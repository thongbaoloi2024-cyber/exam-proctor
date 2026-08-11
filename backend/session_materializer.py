"""Dung thu muc `sessions/<id>/` dung shape docs/DATA_SCHEMAS.md muc 4 tu
phia server, de src/reporting/generate_report() goi duoc y nguyen - KHONG
doi gi trong src/reporting/.

`SESSIONS_ROOT` doc tu bien moi truong (mac dinh "sessions", giong dung quy
uoc cu cua main.py) - trong docker-compose tro toi 1 volume rieng
(`sessions_data`, xem docker-compose.yml) de du lieu khong mat khi container
restart.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from PIL import Image, UnidentifiedImageError

SESSIONS_ROOT = Path(os.environ.get("SESSIONS_ROOT", "sessions"))

_JSONL_FILES = (
    "signals.jsonl",
    "violations.jsonl",
    "risk_score_timeline.jsonl",
    "state_transitions.jsonl",
    "browser_events.jsonl",
)
_MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
_MAX_SNAPSHOT_PIXELS = 20_000_000
_IMAGE_SUFFIX_BY_TYPE = {"image/jpeg": ".jpg", "image/png": ".png"}


def session_dir_for(session_id: str) -> Path:
    return SESSIONS_ROOT / session_id


def ensure_session_dir(session_id: str) -> Path:
    session_dir = session_dir_for(session_id)
    (session_dir / "snapshots").mkdir(parents=True, exist_ok=True)
    for filename in _JSONL_FILES:
        path = session_dir / filename
        if not path.exists():
            path.touch()
    return session_dir


def archive_session_attempt(session_id: str, attempt_number: int) -> Path | None:
    """Move immutable evidence from a failed attempt before reusing its session id."""
    source = session_dir_for(session_id)
    if not source.exists():
        return None
    root = SESSIONS_ROOT.resolve()
    resolved_source = source.resolve()
    if resolved_source.parent != root or resolved_source.name != session_id:
        raise ValueError("Thu muc phien khong hop le")
    archive_parent = root / ".reset_archives" / session_id
    archive_parent.mkdir(parents=True, exist_ok=True)
    destination = archive_parent / f"attempt-{attempt_number}"
    if destination.exists():
        raise ValueError("Ban luu attempt da ton tai")
    resolved_source.replace(destination)
    ensure_session_dir(session_id)
    return destination


def append_jsonl(session_id: str, filename: str, record: Dict[str, Any]) -> None:
    if filename not in _JSONL_FILES:
        raise ValueError("Ten file JSONL khong duoc phep")
    session_dir = ensure_session_dir(session_id)
    with open(session_dir / filename, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_uploaded_snapshot(
    session_id: str,
    event_id: str,
    content_type: str,
    data_base64: str,
    expected_sha256: str,
) -> str:
    """Validate and atomically save one JPEG/PNG uploaded with a violation.

    The caller never controls the destination path.  The returned path is
    relative to the authenticated session directory and is safe to persist
    in ``violations.jsonl``.
    """
    suffix = _IMAGE_SUFFIX_BY_TYPE.get(content_type)
    if suffix is None:
        raise ValueError("Dinh dang anh khong duoc ho tro")
    try:
        raw = base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Du lieu snapshot base64 khong hop le") from exc
    if not raw or len(raw) > _MAX_SNAPSHOT_BYTES:
        raise ValueError("Snapshot rong hoac vuot qua 2 MiB")
    if content_type == "image/jpeg" and not raw.startswith(b"\xff\xd8\xff"):
        raise ValueError("Noi dung khong phai anh JPEG")
    if content_type == "image/png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Noi dung khong phai anh PNG")
    expected_format = "JPEG" if content_type == "image/jpeg" else "PNG"
    try:
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > _MAX_SNAPSHOT_PIXELS:
                raise ValueError("Kich thuoc snapshot khong hop le")
            if image.format != expected_format:
                raise ValueError("Dinh dang snapshot khong khop content type")
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("Snapshot khong phai file anh hop le") from exc
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(actual_sha256, expected_sha256):
        raise ValueError("Checksum snapshot khong khop")

    safe_event_id = "".join(ch for ch in event_id if ch.isalnum() or ch in "_-")
    if not safe_event_id or safe_event_id != event_id or len(safe_event_id) > 64:
        raise ValueError("event_id khong hop le")
    snapshot_dir = ensure_session_dir(session_id) / "snapshots"
    filename = f"evt_{safe_event_id}{suffix}"
    destination = snapshot_dir / filename
    temporary = snapshot_dir / f".{filename}.tmp"
    temporary.write_bytes(raw)
    temporary.replace(destination)
    return f"snapshots/{filename}"


def violation_event_exists(session_id: str, event_id: str) -> bool:
    return event_exists(session_id, "violations.jsonl", event_id)


def browser_event_exists(session_id: str, event_id: str) -> bool:
    return event_exists(session_id, "browser_events.jsonl", event_id)


def event_exists(session_id: str, filename: str, event_id: str) -> bool:
    if filename not in _JSONL_FILES:
        return False
    path = session_dir_for(session_id) / filename
    if not path.is_file():
        return False
    try:
        with open(path, "r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    if json.loads(line).get("event_id") == event_id:
                        return True
                except (json.JSONDecodeError, AttributeError):
                    continue
    except OSError:
        return False
    return False


def write_session_meta(session_id: str, meta: Dict[str, Any]) -> None:
    session_dir = ensure_session_dir(session_id)
    (session_dir / "session_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_session_meta(
    session_id: str,
    started_at: datetime,
    ended_at: datetime,
    fusion_config_version: str = "v1",
    end_reason: str = "completed",
    student_name: str | None = None,
    candidate_number: str | None = None,
    candidate_email: str | None = None,
    authentication_method: str | None = None,
    client_type: str | None = None,
    extension_version: str | None = None,
) -> Dict[str, Any]:
    """Dung chung boi 2 duong ket thuc phien: giam thi ket thuc qua REST
    (`routers/sessions.py`, dung cho truong hop ket thuc ho/force-end) va
    chinh thi sinh ket thuc qua message "end_session" tren WebSocket dang
    dung (`routers/ws.py`) - tranh 2 noi tu xay dict session_meta rieng
    roi lech nhau, dung tinh than voi resolve_severity_thresholds ben
    src/fusion/config.py."""
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if ended_at.tzinfo is None:
        ended_at = ended_at.replace(tzinfo=started_at.tzinfo)
    return {
        "session_id": session_id,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_sec": (ended_at - started_at).total_seconds(),
        "fusion_config_version": fusion_config_version,
        "end_reason": end_reason,
        "student_name": student_name,
        "candidate_number": candidate_number,
        "candidate_email": candidate_email,
        "authentication_method": authentication_method,
        "client_type": client_type,
        "extension_version": extension_version,
    }
