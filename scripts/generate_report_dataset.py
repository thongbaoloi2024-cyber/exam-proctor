"""Sinh dữ liệu tổng hợp quy mô lớn cho dashboard và báo cáo DATT.

Script tạo đồng bộ dữ liệu quan hệ (organization users, memberships, exams,
assignments, sessions, incident reviews) và evidence files trong
``sessions/<session_id>``.  Dữ liệu được cô lập bằng ``batch_id`` và dùng UUID
xác định để tránh va chạm với dữ liệu thật.

Ví dụ:
    python scripts/generate_report_dataset.py --dry-run
    python scripts/generate_report_dataset.py --target-email test@gmail.com
    python scripts/generate_report_dataset.py --session-count 100 --sample-reports 2

Nếu ``REPORT_DATA_PASSWORD`` không được đặt, script sinh một mật khẩu mạnh
ngẫu nhiên và ghi thông tin đăng nhập vào ``generated_reports/<batch>/accounts.csv``.
Chỉ dùng các tài khoản này cho môi trường demo/phát triển.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import random
import re
import secrets
import shutil
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from backend import models  # noqa: E402
from backend.auth import hash_password  # noqa: E402
from backend.db import Base, DATABASE_URL, SessionLocal, engine  # noqa: E402
from backend.db_migrations import apply_additive_migrations  # noqa: E402
from src.reporting.report_generator import generate_report  # noqa: E402


UTC = timezone.utc
NAMESPACE = uuid.UUID("90256b54-b586-4bd0-bb99-fca0eeb74adc")

VIOLATION_SPECS: tuple[tuple[str, str, float, float], ...] = (
    ("FACE_PRESENCE", "FACE_ABSENT", 2.0, 0.0),
    ("MULTI_FACE", "MULTIPLE_FACES", 2.0, 2.0),
    ("EYE_STATE", "EYES_CLOSED", 1.0, 0.16),
    ("MOUTH_STATE", "TALKING", 1.0, 0.48),
    ("OBJECT_PRESENCE", "OBJECT_DETECTED", 2.5, 1.0),
    ("HEAD_POSE", "HEAD_POSE_AWAY", 1.0, 31.0),
    ("IDENTITY", "IDENTITY_MISMATCH", 3.0, 0.34),
)
NORMAL_SIGNAL_VALUES = {
    "FACE_PRESENCE": 1.0,
    "MULTI_FACE": 1.0,
    "EYE_STATE": 0.29,
    "MOUTH_STATE": 0.08,
    "OBJECT_PRESENCE": 0.0,
    "HEAD_POSE": 3.0,
    "IDENTITY": 0.82,
}
BROWSER_SEVERITY = {
    "MEDIA_READY": "LOW",
    "CONTENT_MONITOR_READY": "LOW",
    "TAB_HIDDEN": "LOW",
    "TAB_VISIBLE": "LOW",
    "WINDOW_BLUR": "LOW",
    "WINDOW_FOCUS": "LOW",
    "TAB_SWITCHED": "MEDIUM",
    "NEW_TAB": "MEDIUM",
    "NAVIGATION_AWAY": "HIGH",
    "FULLSCREEN_EXIT": "HIGH",
    "FULLSCREEN_ENTER": "LOW",
    "CLIPBOARD_COPY": "MEDIUM",
    "CLIPBOARD_PASTE": "MEDIUM",
    "CONTEXT_MENU": "MEDIUM",
    "CAMERA_MUTED": "HIGH",
    "CAMERA_ENDED": "HIGH",
    "MICROPHONE_MUTED": "HIGH",
    "MICROPHONE_ENDED": "HIGH",
    "SCREEN_SHARE_ENDED": "HIGH",
    "MONITOR_CLOSED": "HIGH",
    "PERMISSION_MISSING": "HIGH",
}
PROFILE_WEIGHTS = (("normal", 0.20), ("low", 0.25), ("medium", 0.30), ("high", 0.25))
VIOLATION_RANGES = {
    "normal": (0, 0),
    "low": (5, 10),
    "medium": (12, 22),
    "high": (25, 40),
}
BROWSER_RANGES = {
    "normal": (0, 2),
    "low": (2, 5),
    "medium": (5, 10),
    "high": (10, 18),
}
FIRST_NAMES = (
    "An", "Bình", "Chi", "Dũng", "Giang", "Hà", "Hải", "Hiếu", "Hương", "Khánh",
    "Lan", "Linh", "Long", "Mai", "Minh", "Nam", "Ngân", "Ngọc", "Phương", "Quân",
    "Sơn", "Thảo", "Trang", "Trung", "Tuấn", "Vy",
)
LAST_NAMES = ("Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ")
MIDDLE_NAMES = (
    "Văn", "Thị", "Minh", "Ngọc", "Quốc", "Thanh", "Đức", "Thu", "Hoàng", "Anh",
    "Gia", "Hải", "Khánh", "Phương", "Quang", "Tuấn", "Hữu", "Bảo", "Mai", "Thùy",
)
EXAM_NAMES = (
    "Nhập môn Trí tuệ nhân tạo", "Cấu trúc dữ liệu và giải thuật",
    "Cơ sở dữ liệu", "Mạng máy tính", "Lập trình Python",
    "An toàn thông tin", "Xử lý ảnh số", "Kỹ thuật phần mềm",
    "Toán rời rạc", "Hệ điều hành", "Phân tích dữ liệu", "Điện toán đám mây",
)
STAFF_IDENTITIES = {
    "org_admin": (
        ("Nguyễn Minh Anh", "nguyen.minh.anh"),
        ("Trần Thu Hà", "tran.thu.ha"),
        ("Lê Quốc Bảo", "le.quoc.bao"),
    ),
    "manager": (
        ("Phạm Ngọc Lan", "pham.ngoc.lan"),
        ("Vũ Minh Quân", "vu.minh.quan"),
        ("Đặng Thùy Linh", "dang.thuy.linh"),
        ("Bùi Hoàng Nam", "bui.hoang.nam"),
    ),
    "proctor": (
        ("Đỗ Quang Hải", "do.quang.hai"),
        ("Nguyễn Mai Trang", "nguyen.mai.trang"),
        ("Trần Anh Dũng", "tran.anh.dung"),
        ("Lê Thanh Mai", "le.thanh.mai"),
        ("Phạm Đức Sơn", "pham.duc.son"),
    ),
}


@dataclass(frozen=True)
class Config:
    batch_id: str
    target_email: str
    exam_count: int
    session_count: int
    days: int
    seed: int
    org_admins: int
    managers: int
    proctors: int
    snapshot_rate: float
    sample_reports: int
    report_formats: tuple[str, ...]
    sessions_root: Path
    output_root: Path
    password: str
    dry_run: bool
    staff_domain: str
    student_domain: str
    exam_domain: str
    refresh_existing: bool


@dataclass
class GenerationStats:
    organization_id: str = ""
    organization_name: str = ""
    users: list[dict[str, Any]] = field(default_factory=list)
    exams: list[dict[str, Any]] = field(default_factory=list)
    sessions: list[dict[str, Any]] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    browser_events: int = 0
    incident_reviews: int = 0
    snapshots: int = 0
    session_ids: list[str] = field(default_factory=list)
    report_jobs: int = 0
    reports: list[dict[str, str]] = field(default_factory=list)


def stable_id(batch_id: str, kind: str, key: str | int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{batch_id}:{kind}:{key}"))


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def choose_weighted(rng: random.Random, weighted: Sequence[tuple[str, float]]) -> str:
    marker = rng.random()
    total = 0.0
    for name, weight in weighted:
        total += weight
        if marker <= total:
            return name
    return weighted[-1][0]


def sanitize_batch_id(raw: str) -> str:
    value = raw.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,39}", value):
        raise argparse.ArgumentTypeError("batch-id phải dài 3-40 ký tự: a-z, 0-9, _ hoặc -")
    return value


def staff_identity(group: str, index: int, domain: str) -> tuple[str, str]:
    profiles = STAFF_IDENTITIES[group]
    display_name, local_part = profiles[index % len(profiles)]
    cycle = index // len(profiles)
    if cycle:
        local_part = f"{local_part}.{cycle + 1}"
    return display_name, f"{local_part}@{domain}"


def student_identity(index: int, domain: str) -> tuple[str, str, str]:
    """Return a deterministic, unique-enough Vietnamese student profile.

    The permutation spreads first/middle/last names across the dataset instead
    of visibly repeating the same short list every few rows.
    """
    combinations = len(LAST_NAMES) * len(MIDDLE_NAMES) * len(FIRST_NAMES)
    code = (index * 37) % combinations
    last_name = LAST_NAMES[code % len(LAST_NAMES)]
    code //= len(LAST_NAMES)
    middle_name = MIDDLE_NAMES[code % len(MIDDLE_NAMES)]
    code //= len(MIDDLE_NAMES)
    first_name = FIRST_NAMES[code % len(FIRST_NAMES)]
    display_name = f"{last_name} {middle_name} {first_name}"
    cohort = 21 + index % 5
    faculty = 1 + (index // 5) % 8
    candidate_number = f"{cohort:02d}{faculty:02d}{index + 1:04d}"
    return display_name, candidate_number, f"{candidate_number}@{domain}"


def exam_title(index: int, scheduled_start: datetime) -> str:
    semester = 1 if scheduled_start.month >= 8 or scheduled_start.month == 1 else 2
    academic_start = scheduled_start.year if scheduled_start.month >= 8 else scheduled_start.year - 1
    academic_year = f"{academic_start}–{academic_start + 1}"
    return f"Thi cuối kỳ - {EXAM_NAMES[index % len(EXAM_NAMES)]} - Học kỳ {semester}, {academic_year}"


def google_subject(batch_id: str, index: int) -> str:
    digest = hashlib.sha256(f"{batch_id}:google-subject:{index}".encode()).digest()
    return str(int.from_bytes(digest[:9], "big"))[:21]


def csv_write(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def jsonl_write(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def snapshot_bytes(severity: str) -> bytes:
    colors = {"LOW": "#15803d", "MEDIUM": "#d97706", "HIGH": "#b91c1c"}
    image = Image.new("RGB", (640, 360), colors[severity])
    draw = ImageDraw.Draw(image)
    draw.rectangle((25, 25, 615, 335), outline="white", width=4)
    draw.text((55, 125), "PROCTORING CAMERA RECORD", fill="white")
    draw.text((55, 165), f"Risk level: {severity}", fill="white")
    draw.text((55, 205), "Frame captured automatically", fill="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def signal_metadata(signal_name: str, value: float, timestamp: float) -> dict[str, Any]:
    if signal_name == "FACE_PRESENCE":
        return {"consecutive_absent_sec": 3.2 if value == 0 else 0.0}
    if signal_name == "MULTI_FACE":
        return {"face_count": int(value)}
    if signal_name == "EYE_STATE":
        return {"ear_left": value, "ear_right": round(value + 0.01, 3)}
    if signal_name == "MOUTH_STATE":
        return {"mouth_open_ratio": value, "activity_ratio": min(1.0, value + 0.12)}
    if signal_name == "OBJECT_PRESENCE":
        return {"object_class": "cell phone" if value else None, "confidence": 0.93}
    if signal_name == "HEAD_POSE":
        return {"yaw": value, "pitch": round(value / 5, 2), "roll": 1.2}
    return {"cosine_similarity": value, "last_verified_at": timestamp}


def make_signal_row(
    signal_name: str,
    value: float,
    timestamp: float,
    *,
    exceeds: bool,
    state: str,
) -> dict[str, Any]:
    return {
        "signal_name": signal_name,
        "timestamp": round(timestamp, 3),
        "value": value,
        "exceeds_threshold": exceeds,
        "confidence": 0.94,
        "state": state,
        "metadata": signal_metadata(signal_name, value, timestamp),
    }


def make_browser_events(
    rng: random.Random,
    config: Config,
    session_id: str,
    started_at: datetime,
    duration_sec: float,
    count: int,
) -> list[dict[str, Any]]:
    event_types = tuple(BROWSER_SEVERITY)
    if count <= 0:
        return []
    times = sorted(rng.uniform(5.0, max(6.0, duration_sec - 2.0)) for _ in range(count))
    rows: list[dict[str, Any]] = []
    for sequence, video_time in enumerate(times):
        event_type = rng.choice(event_types)
        timestamp = started_at + timedelta(seconds=video_time)
        duration_ms = rng.randint(800, 18_000) if event_type in {
            "TAB_HIDDEN", "WINDOW_BLUR", "TAB_SWITCHED", "FULLSCREEN_EXIT"
        } else None
        severity = BROWSER_SEVERITY[event_type]
        if duration_ms and duration_ms > 5_000:
            severity = "HIGH"
        rows.append({
            "event_id": stable_id(config.batch_id, "browser-event", f"{session_id}:{sequence}"),
            "sequence": sequence,
            "event_type": event_type,
            "client_timestamp": iso(timestamp - timedelta(milliseconds=rng.randint(20, 250))),
            "observed_origin": f"https://{config.exam_domain}",
            "duration_ms": duration_ms,
            "metadata": {"source": "browser_extension"},
            "timestamp": iso(timestamp),
            "video_time_sec": round(video_time, 3),
            "severity": severity,
            "server_duration_ms": duration_ms,
            "snapshot_path": None,
            "server_received_at": iso(timestamp),
        })
    return rows


def make_session_evidence(
    config: Config,
    rng: random.Random,
    session_id: str,
    student_name: str,
    candidate_number: str,
    candidate_email: str | None,
    authentication_method: str,
    client_type: str,
    extension_version: str | None,
    profile: str,
    started_at: datetime,
    ended_at: datetime | None,
    duration_sec: float,
    snapshot_payloads: dict[str, bytes],
) -> tuple[dict[str, Any], list[dict[str, Any]], int, int]:
    session_dir = config.sessions_root / session_id
    snapshot_dir = session_dir / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=False)

    violation_count = rng.randint(*VIOLATION_RANGES[profile])
    violation_times = sorted(
        rng.uniform(15.0, max(16.0, duration_sec - 10.0)) for _ in range(violation_count)
    )
    violations: list[dict[str, Any]] = []
    signals = [
        make_signal_row(name, value, started_at.timestamp(), exceeds=False, state="NORMAL")
        for name, value in NORMAL_SIGNAL_VALUES.items()
    ]
    transitions: list[dict[str, Any]] = []
    snapshots = 0

    for index, video_time in enumerate(violation_times):
        signal_name, violation_type, weight, signal_value = rng.choice(VIOLATION_SPECS)
        is_high = profile == "high" and rng.random() < 0.72 or profile == "medium" and rng.random() < 0.25
        risk_score = round(rng.uniform(10.0, 15.0) if is_high else rng.uniform(5.0, 9.9), 2)
        severity = "HIGH" if risk_score >= 10.0 else "MEDIUM"
        event_id = stable_id(config.batch_id, "violation", f"{session_id}:{index}")
        event_at = started_at + timedelta(seconds=video_time)
        contributions = [{
            "signal_name": signal_name,
            "violation_type": violation_type,
            "state": "ALERT",
            "value": signal_value,
            "weight": weight,
        }]
        if rng.random() < (0.50 if profile == "high" else 0.22):
            secondary = rng.choice([item for item in VIOLATION_SPECS if item[0] != signal_name])
            contributions.append({
                "signal_name": secondary[0],
                "violation_type": secondary[1],
                "state": "SUSPICIOUS",
                "value": secondary[3],
                "weight": secondary[2],
            })
        snapshot_path = None
        if rng.random() < config.snapshot_rate:
            filename = f"evt_{event_id}.png"
            (snapshot_dir / filename).write_bytes(snapshot_payloads[severity])
            snapshot_path = f"snapshots/{filename}"
            snapshots += 1
        violations.append({
            "event_id": event_id,
            "session_id": session_id,
            "video_time_sec": round(video_time, 3),
            "timestamp": iso(event_at),
            "risk_score": risk_score,
            "severity": severity,
            "primary_violation": violation_type,
            "contributing_signals": contributions,
            "snapshot_path": snapshot_path,
            "metadata": {"fusion_config_version": "v1", "capture_source": "risk_fusion_engine"},
        })
        signals.append(make_signal_row(
            signal_name, signal_value, event_at.timestamp(), exceeds=True, state="ALERT"
        ))
        transitions.extend((
            {
                "timestamp": event_at.timestamp(), "scope": "signal", "signal_name": signal_name,
                "from_state": "NORMAL", "to_state": "ALERT", "exceed_ratio": round(rng.uniform(0.62, 1.0), 2),
            },
            {
                "timestamp": event_at.timestamp(), "scope": "session",
                "from_state": "SESSION_NORMAL", "to_state": "SESSION_ALERT", "risk_score": risk_score,
            },
            {
                "timestamp": (event_at + timedelta(seconds=4)).timestamp(), "scope": "session",
                "from_state": "SESSION_ALERT", "to_state": "SESSION_NORMAL", "risk_score": round(rng.uniform(0.0, 2.4), 2),
            },
        ))

    browser_count = rng.randint(*BROWSER_RANGES[profile]) if client_type == "browser_extension" else 0
    browser_events = make_browser_events(
        rng, config, session_id, started_at, duration_sec, browser_count
    )
    risk_rows: list[dict[str, Any]] = []
    for second in range(0, max(1, int(duration_sec)) + 1, 30):
        nearby = [item["risk_score"] for item in violations if abs(item["video_time_sec"] - second) <= 20]
        baseline_max = {"normal": 1.2, "low": 2.8, "medium": 4.2, "high": 5.5}[profile]
        score = max(nearby, default=rng.uniform(0.0, baseline_max))
        risk_rows.append({
            "timestamp": (started_at + timedelta(seconds=second)).timestamp(),
            "video_time_sec": float(second),
            "risk_score": round(score, 2),
            "session_state": "SESSION_ALERT" if score >= 5.0 else "SESSION_NORMAL",
        })

    meta_end = ended_at or started_at + timedelta(seconds=duration_sec)
    meta = {
        "session_id": session_id,
        "started_at": iso(started_at),
        "ended_at": iso(meta_end) if ended_at else None,
        "duration_sec": round(duration_sec, 3),
        "fusion_config_version": "v1",
        "end_reason": "completed" if ended_at else None,
        "student_name": student_name,
        "candidate_number": candidate_number,
        "candidate_email": candidate_email,
        "authentication_method": authentication_method,
        "client_type": client_type,
        "extension_version": extension_version,
    }
    (session_dir / "session_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    jsonl_write(session_dir / "signals.jsonl", signals)
    jsonl_write(session_dir / "state_transitions.jsonl", transitions)
    jsonl_write(session_dir / "violations.jsonl", violations)
    jsonl_write(session_dir / "browser_events.jsonl", browser_events)
    jsonl_write(session_dir / "risk_score_timeline.jsonl", risk_rows)
    return meta, violations, browser_count, snapshots


def create_users(
    db: Any,
    config: Config,
    org: models.Organization,
    invited_by_user_id: str,
    password_hash: str,
) -> tuple[list[models.User], list[models.User], list[models.User], list[dict[str, Any]]]:
    groups: dict[str, list[models.User]] = {"org_admin": [], "manager": [], "proctor": []}
    rows: list[dict[str, Any]] = []
    counts = {"org_admin": config.org_admins, "manager": config.managers, "proctor": config.proctors}
    for group, count in counts.items():
        membership_role = "org_admin" if group == "org_admin" else "exam_manager"
        legacy_role = "admin" if group == "org_admin" else "proctor"
        for index in range(count):
            number = index + 1
            display_name, email = staff_identity(group, index, config.staff_domain)
            user_id = stable_id(config.batch_id, "user", f"{group}:{number}")
            if db.get(models.User, user_id) or db.query(models.User).filter_by(email=email).first():
                raise RuntimeError(f"Batch đã tồn tại hoặc email bị trùng: {email}")
            user = models.User(
                id=user_id,
                org_id=org.id,
                email=email,
                display_name=display_name,
                password_hash=password_hash,
                role=legacy_role,
                status="active",
                mfa_enabled=False,
            )
            db.add(user)
            db.flush()
            db.add(models.OrganizationMembership(
                id=stable_id(config.batch_id, "membership", f"{group}:{number}"),
                user_id=user.id,
                org_id=org.id,
                role=membership_role,
                status="active",
                invited_by_user_id=invited_by_user_id,
            ))
            groups[group].append(user)
            rows.append({
                "email": email,
                "password": config.password,
                "display_name": user.display_name,
                "organization_role": membership_role,
                "exam_role": "proctor" if group == "proctor" else ("owner/manager" if group == "manager" else "none"),
                "purpose": "Quản trị tổ chức" if group == "org_admin" else ("Quản lý kỳ thi" if group == "manager" else "Giám sát kỳ thi"),
            })
    return groups["org_admin"], groups["manager"], groups["proctor"], rows


def exam_status(index: int, exam_count: int) -> str:
    if index == 0:
        return "draft"
    if index == 1 and exam_count >= 5:
        return "scheduled"
    if index in {exam_count - 2, exam_count - 1}:
        return "open"
    if index == 2 and exam_count >= 6:
        return "archived"
    return "closed"


def make_join_code(batch_id: str, index: int) -> str:
    digest = hashlib.sha256(f"{batch_id}:exam:{index}".encode()).hexdigest().upper()
    return digest[:10]


def create_exams_and_assignments(
    db: Any,
    config: Config,
    org: models.Organization,
    managers: list[models.User],
    proctors: list[models.User],
    now: datetime,
) -> tuple[list[models.Exam], list[dict[str, Any]]]:
    exams: list[models.Exam] = []
    exam_rows: list[dict[str, Any]] = []
    for index in range(config.exam_count):
        owner = managers[index % len(managers)]
        status = exam_status(index, config.exam_count)
        exam_id = stable_id(config.batch_id, "exam", index)
        if db.get(models.Exam, exam_id):
            raise RuntimeError(f"Batch đã tồn tại: exam {exam_id}")
        if status == "scheduled":
            scheduled_start = now + timedelta(days=7)
        elif status in {"open", "draft"}:
            scheduled_start = now - timedelta(hours=1)
        else:
            scheduled_start = now - timedelta(days=max(1, config.days * (index + 1) / config.exam_count))
        scheduled_end = scheduled_start + timedelta(hours=2)
        exam = models.Exam(
            id=exam_id,
            org_id=org.id,
            name=exam_title(index, scheduled_start),
            join_code=make_join_code(config.batch_id, index),
            status=status,
            join_code_expires_at=now + timedelta(days=30),
            candidate_auth_mode="google" if index % 3 == 0 else "manual",
            exam_url=f"https://{config.exam_domain}/exams/{make_join_code(config.batch_id, index).lower()}",
            require_extension=index % 2 == 0,
            min_extension_version="1.0.0",
            require_fullscreen=True,
            require_camera=True,
            require_microphone=index % 3 == 0,
            require_screen_share=index % 4 == 0,
            block_clipboard=True,
            max_focus_loss_seconds=5.0,
            google_allowed_domain=config.student_domain if index % 3 == 0 else None,
            created_by_user_id=owner.id,
            owner_user_id=owner.id,
            scheduled_start_at=scheduled_start,
            scheduled_end_at=scheduled_end,
            archived_at=now - timedelta(days=2) if status == "archived" else None,
            created_at=scheduled_start - timedelta(days=14),
            updated_at=now,
        )
        db.add(exam)
        db.flush()
        assignment_specs: list[tuple[models.User, str]] = [(owner, "owner")]
        assignment_specs.append((managers[(index + 1) % len(managers)], "manager"))
        if len(managers) > 2 and index % 2 == 0:
            assignment_specs.append((managers[(index + 2) % len(managers)], "manager"))
        assignment_specs.extend((proctors[(index + offset) % len(proctors)], "proctor") for offset in range(min(2, len(proctors))))
        seen: set[str] = set()
        assigned_labels: list[str] = []
        for user, role in assignment_specs:
            if user.id in seen:
                continue
            seen.add(user.id)
            db.add(models.ExamAssignment(
                id=stable_id(config.batch_id, "assignment", f"{exam.id}:{user.id}"),
                exam_id=exam.id,
                user_id=user.id,
                assignment_role=role,
                status="active",
                assigned_by_user_id=owner.id,
                is_pinned=role == "owner" and index < 4,
                pinned_at=now if role == "owner" and index < 4 else None,
            ))
            assigned_labels.append(f"{user.email}:{role}")
        db.add(models.AuditLog(
            id=stable_id(config.batch_id, "audit", f"exam-create:{index}"),
            actor_user_id=owner.id,
            actor_role="exam_manager",
            org_id=org.id,
            exam_id=exam.id,
            action="exam.create",
            resource_type="exam",
            resource_id=exam.id,
            outcome="success",
            reason="Khởi tạo kỳ thi theo kế hoạch đào tạo",
            after_json=json.dumps({"status": status}, ensure_ascii=False),
            created_at=exam.created_at,
        ))
        exams.append(exam)
        exam_rows.append({
            "exam_id": exam.id,
            "exam_name": exam.name,
            "status": status,
            "owner_email": owner.email,
            "candidate_auth_mode": exam.candidate_auth_mode,
            "scheduled_start_at": iso(scheduled_start),
            "scheduled_end_at": iso(scheduled_end),
            "assignments": "; ".join(assigned_labels),
        })
    return exams, exam_rows


def create_candidate_identities(db: Any, config: Config, now: datetime) -> list[models.CandidateIdentity]:
    pool_size = max(50, min(config.session_count, (config.session_count // max(1, config.exam_count)) + 20))
    identities: list[models.CandidateIdentity] = []
    for index in range(pool_size):
        candidate_id = stable_id(config.batch_id, "candidate", index)
        display_name, candidate_number, email = student_identity(index, config.student_domain)
        identity = models.CandidateIdentity(
            id=candidate_id,
            provider="google",
            provider_subject=google_subject(config.batch_id, index),
            email=email,
            email_verified=True,
            display_name=display_name,
            hosted_domain=config.student_domain,
            created_at=now - timedelta(days=config.days),
            updated_at=now,
            last_login_at=now - timedelta(days=index % max(1, config.days)),
        )
        db.add(identity)
        db.flush()
        db.add(models.CandidateDevice(
            id=stable_id(config.batch_id, "candidate-device", index),
            candidate_identity_id=identity.id,
            device_id_hash=hashlib.sha256(f"{config.batch_id}:device:{index}".encode()).hexdigest(),
            token_hash=hashlib.sha256(f"{config.batch_id}:token:{index}".encode()).hexdigest(),
            created_at=identity.created_at,
            last_used_at=identity.last_login_at,
            expires_at=now + timedelta(days=365),
        ))
        identities.append(identity)
    return identities


def active_exam_indices(exams: Sequence[models.Exam]) -> list[int]:
    indices = [index for index, exam in enumerate(exams) if exam.status not in {"draft", "scheduled"}]
    return indices or list(range(len(exams)))


def create_sessions(
    db: Any,
    config: Config,
    org: models.Organization,
    exams: list[models.Exam],
    identities: list[models.CandidateIdentity],
    managers: list[models.User],
    proctors: list[models.User],
    now: datetime,
    stats: GenerationStats,
) -> None:
    snapshot_payloads = {severity: snapshot_bytes(severity) for severity in ("LOW", "MEDIUM", "HIGH")}
    eligible_exam_indices = active_exam_indices(exams)
    sessions_per_exam: Counter[int] = Counter()
    reviewed_audits = 0
    for index in range(config.session_count):
        rng = random.Random(config.seed * 1_000_003 + index)
        exam_index = eligible_exam_indices[index % len(eligible_exam_indices)]
        exam = exams[exam_index]
        ordinal = sessions_per_exam[exam_index]
        sessions_per_exam[exam_index] += 1
        session_id = stable_id(config.batch_id, "session", index)
        if db.get(models.ExamSession, session_id) or (config.sessions_root / session_id).exists():
            raise RuntimeError(f"Batch đã tồn tại hoặc thư mục phiên bị trùng: {session_id}")
        profile = choose_weighted(rng, PROFILE_WEIGHTS)
        student_name, candidate_number, student_email = student_identity(ordinal, config.student_domain)
        uses_google = exam.candidate_auth_mode == "google" and ordinal < len(identities)
        identity = identities[ordinal % len(identities)] if uses_google else None
        candidate_email = identity.email if identity else student_email
        authentication_method = "google" if identity else "manual"
        client_type = "browser_extension" if exam.require_extension or index % 3 != 0 else "desktop_cv"
        extension_version = rng.choice(("1.0.0", "1.1.0", "1.2.0")) if client_type == "browser_extension" else None

        is_open = exam.status == "open"
        live_slot = index % 50
        if is_open and live_slot == 0:
            status = "active"
            started_at = now - timedelta(seconds=rng.randint(5, 45))
            duration_sec = max(10.0, (now - started_at).total_seconds())
            ended_at = None
            last_seen_at = now - timedelta(seconds=rng.randint(0, 5))
            disconnect_reason = None
        elif is_open and live_slot == 1:
            status = "pending"
            started_at = now - timedelta(seconds=rng.randint(5, 45))
            duration_sec = max(10.0, (now - started_at).total_seconds())
            ended_at = None
            last_seen_at = started_at
            disconnect_reason = None
        else:
            days_ago = rng.uniform(1.0, float(config.days))
            started_at = now - timedelta(days=days_ago, hours=rng.uniform(0, 18))
            duration_sec = float(rng.randint(45, 120) * 60)
            ended_at = started_at + timedelta(seconds=duration_sec)
            if index % 25 == 0:
                status = "disconnected"
                disconnect_reason = rng.choice(("network_timeout", "browser_closed", "client_idle_timeout"))
            else:
                status = "ended"
                disconnect_reason = "completed"
            last_seen_at = ended_at - timedelta(seconds=rng.randint(0, 30))

        # Register the exact target before filesystem materialization so a
        # failure while writing the first file of this session is recoverable.
        stats.session_ids.append(session_id)
        meta, violations, browser_count, snapshots = make_session_evidence(
            config, rng, session_id, student_name, candidate_number, candidate_email,
            authentication_method, client_type, extension_version, profile,
            started_at, ended_at, duration_sec, snapshot_payloads,
        )
        integrity_score = min(100.0, sum(
            20.0 if event["severity"] == "HIGH" else 5.0 if event["severity"] == "MEDIUM" else 0.0
            for event in _read_jsonl(config.sessions_root / session_id / "browser_events.jsonl")
        ))
        integrity_status = "alert" if integrity_score >= 20 else "warning" if integrity_score >= 5 else "healthy"
        peak_risk = max((event["risk_score"] for event in violations), default=round(rng.uniform(0, 2.4), 2))
        session_state = "SESSION_ALERT" if status == "active" and peak_risk >= 5 else "SESSION_NORMAL"
        exam_session = models.ExamSession(
            id=session_id,
            exam_id=exam.id,
            student_name=student_name,
            candidate_number=candidate_number,
            candidate_email=candidate_email,
            candidate_identity_id=identity.id if identity else None,
            authentication_method=authentication_method,
            client_type=client_type,
            extension_version=extension_version,
            browser_name=rng.choice(("Chrome", "Firefox", "Edge")) if client_type == "browser_extension" else None,
            browser_version=str(rng.randint(124, 140)) if client_type == "browser_extension" else None,
            platform=rng.choice(("Windows 11", "Ubuntu 24.04", "macOS 15")),
            capabilities_json=json.dumps(["camera", "content_monitor", "storage_session"] if client_type == "browser_extension" else ["camera"]),
            device_id_hash=hashlib.sha256(f"{config.batch_id}:{session_id}".encode()).hexdigest(),
            camera_status="ready",
            microphone_status="ready" if exam.require_microphone else "not_required",
            screen_share_status="ready" if exam.require_screen_share else "not_required",
            reset_count=1 if index % 97 == 0 else 0,
            last_reset_at=started_at - timedelta(minutes=3) if index % 97 == 0 else None,
            last_reset_reason="Mất kết nối trước khi bắt đầu" if index % 97 == 0 else None,
            status=status,
            risk_score_current=peak_risk,
            session_state_current=session_state,
            started_at=started_at,
            ended_at=ended_at,
            last_seen_at=last_seen_at,
            disconnect_reason=disconnect_reason,
            integrity_score_current=integrity_score,
            integrity_status_current=integrity_status,
            browser_event_count=browser_count,
        )
        db.add(exam_session)
        db.flush()

        for violation_index, violation in enumerate(violations):
            if rng.random() > 0.55:
                review_status = "new"
                reviewer = None
                reviewed_at = None
                note = None
            else:
                review_status = rng.choices(
                    ("new", "in_review", "confirmed", "dismissed"), weights=(20, 20, 40, 20), k=1
                )[0]
                reviewer = rng.choice(proctors + managers) if review_status != "new" else None
                reviewed_at = (started_at + timedelta(seconds=violation["video_time_sec"] + 120)) if reviewer else None
                note = {
                    "in_review": "Đang đối chiếu bằng chứng và nhật ký trình duyệt.",
                    "confirmed": "Đã xác nhận sự kiện cần ghi nhận trong biên bản.",
                    "dismissed": "Loại trừ sau khi giám thị kiểm tra ngữ cảnh.",
                }.get(review_status)
            if review_status != "new":
                review = models.IncidentReview(
                    id=stable_id(config.batch_id, "review", f"{session_id}:{violation_index}"),
                    exam_session_id=session_id,
                    violation_event_id=violation["event_id"],
                    status=review_status,
                    note=note,
                    reviewed_by_user_id=reviewer.id if reviewer else None,
                    created_at=started_at + timedelta(seconds=violation["video_time_sec"]),
                    updated_at=reviewed_at or started_at,
                    reviewed_at=reviewed_at,
                )
                db.add(review)
                stats.incident_reviews += 1
                if reviewed_audits < 250:
                    db.add(models.AuditLog(
                        id=stable_id(config.batch_id, "audit-review", f"{session_id}:{violation_index}"),
                        actor_user_id=reviewer.id if reviewer else None,
                        actor_role="proctor" if reviewer in proctors else "exam_manager",
                        org_id=org.id,
                        exam_id=exam.id,
                        action="exam.incident.review",
                        resource_type="violation_event",
                        resource_id=violation["event_id"],
                        outcome="success",
                        reason="Cập nhật kết quả rà soát sự kiện",
                        after_json=json.dumps({"status": review_status}),
                        created_at=reviewed_at or started_at,
                    ))
                    reviewed_audits += 1

            stats.violations.append({
                "exam_id": exam.id,
                "session_id": session_id,
                "event_id": violation["event_id"],
                "student_name": student_name,
                "profile": profile,
                "video_time_sec": violation["video_time_sec"],
                "violation_type": violation["primary_violation"],
                "severity": violation["severity"],
                "risk_score": violation["risk_score"],
                "review_status": review_status,
                "timestamp": violation["timestamp"],
            })
        stats.browser_events += browser_count
        stats.snapshots += snapshots
        stats.sessions.append({
            "session_id": session_id,
            "exam_id": exam.id,
            "exam_name": exam.name,
            "student_name": student_name,
            "candidate_number": candidate_number,
            "candidate_email": candidate_email,
            "authentication_method": authentication_method,
            "client_type": client_type,
            "status": status,
            "risk_profile": profile,
            "risk_score_peak": peak_risk,
            "integrity_score": integrity_score,
            "violation_count": len(violations),
            "browser_event_count": browser_count,
            "started_at": iso(started_at),
            "ended_at": meta["ended_at"],
            "duration_sec": duration_sec,
        })


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def refresh_output_files(
    config: Config,
    database_backup: Path | None,
    email_map: dict[str, str],
    staff_by_email: dict[str, dict[str, str]],
    exam_updates: dict[str, dict[str, str]],
    session_updates: dict[str, dict[str, str]],
) -> Path:
    output_dir = config.output_root / config.batch_id
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Không tìm thấy manifest của batch: {manifest_path}")
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    backup_dir = config.output_root / f"{config.batch_id}-pre-refresh-{stamp}"
    shutil.copytree(output_dir, backup_dir)

    account_rows = _read_csv(output_dir / "accounts.csv")
    for row in account_rows:
        row["email"] = email_map.get(row["email"], row["email"])
        profile = staff_by_email.get(row["email"])
        if profile:
            row["display_name"] = profile["display_name"]
    csv_write(output_dir / "accounts.csv", tuple(account_rows[0]), account_rows)

    exam_rows = _read_csv(output_dir / "exams.csv")
    for row in exam_rows:
        update = exam_updates.get(row["exam_id"])
        if update:
            row["exam_name"] = update["exam_name"]
            row["owner_email"] = email_map.get(row["owner_email"], row["owner_email"])
            assignments = row.get("assignments", "")
            for old_email, new_email in email_map.items():
                assignments = assignments.replace(old_email, new_email)
            row["assignments"] = assignments
    csv_write(output_dir / "exams.csv", tuple(exam_rows[0]), exam_rows)

    session_rows = _read_csv(output_dir / "sessions.csv")
    for row in session_rows:
        update = session_updates.get(row["session_id"])
        if update:
            row.update(update)
    csv_write(output_dir / "sessions.csv", tuple(session_rows[0]), session_rows)

    violation_rows = _read_csv(output_dir / "violations.csv")
    for row in violation_rows:
        update = session_updates.get(row["session_id"])
        if update:
            row["student_name"] = update["student_name"]
    csv_write(output_dir / "violations.csv", tuple(violation_rows[0]), violation_rows)

    exam_summary_rows = _read_csv(output_dir / "exam_summary.csv")
    for row in exam_summary_rows:
        update = exam_updates.get(row["exam_id"])
        if update:
            row["exam_name"] = update["exam_name"]
            row["owner_email"] = email_map.get(row["owner_email"], row["owner_email"])
    csv_write(output_dir / "exam_summary.csv", tuple(exam_summary_rows[0]), exam_summary_rows)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["refreshed_at"] = iso(utc_now())
    manifest["display_profile"] = "realistic_v1"
    manifest["refresh_database_backup"] = str(database_backup) if database_backup else None
    manifest["refresh_output_backup"] = str(backup_dir)
    manifest["configuration"].update({
        "staff_domain": config.staff_domain,
        "student_domain": config.student_domain,
        "exam_domain": config.exam_domain,
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup_dir


def refresh_existing_dataset(config: Config) -> tuple[dict[str, int], Path | None, Path]:
    """Refresh display data for one deterministic batch without changing IDs/counts."""
    output_dir = config.output_root / config.batch_id
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Không tìm thấy batch hiện có: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_sessions = int(manifest.get("counts", {}).get("sessions", config.session_count))
    if expected_sessions != config.session_count:
        raise RuntimeError(
            f"session-count phải khớp manifest hiện có: {config.session_count} != {expected_sessions}"
        )
    Base.metadata.create_all(bind=engine)
    apply_additive_migrations(engine)
    database_backup = backup_sqlite_database(f"{config.batch_id}-pre-refresh")
    snapshot_payloads = {severity: snapshot_bytes(severity) for severity in ("LOW", "MEDIUM", "HIGH")}
    email_map: dict[str, str] = {}
    staff_by_email: dict[str, dict[str, str]] = {}
    exam_updates: dict[str, dict[str, str]] = {}
    session_updates: dict[str, dict[str, str]] = {}
    refreshed_snapshots = 0
    output_backup: Path | None = None

    with SessionLocal() as db:
        target_user = db.query(models.User).filter(models.User.email == config.target_email).first()
        if target_user is None:
            raise RuntimeError(f"Không tìm thấy tài khoản mục tiêu: {config.target_email}")
        membership = db.query(models.OrganizationMembership).filter_by(
            user_id=target_user.id, org_id=target_user.org_id, status="active"
        ).first()
        if membership is None:
            raise RuntimeError("Tài khoản mục tiêu không có membership hoạt động")
        org = db.get(models.Organization, membership.org_id)
        if org is None:
            raise RuntimeError("Không tìm thấy tổ chức của tài khoản mục tiêu")

        for group, count in (
            ("org_admin", config.org_admins), ("manager", config.managers), ("proctor", config.proctors)
        ):
            for index in range(count):
                user_id = stable_id(config.batch_id, "user", f"{group}:{index + 1}")
                user = db.get(models.User, user_id)
                if user is None or user.org_id != org.id:
                    raise RuntimeError(f"Không tìm thấy user của batch: {user_id}")
                display_name, new_email = staff_identity(group, index, config.staff_domain)
                collision = db.query(models.User).filter(
                    models.User.email == new_email, models.User.id != user.id
                ).first()
                if collision:
                    raise RuntimeError(f"Email thực tế đã được dùng bởi tài khoản khác: {new_email}")
                email_map[user.email] = new_email
                user.email = new_email
                user.display_name = display_name
                staff_by_email[new_email] = {"display_name": display_name, "group": group}

        exams: list[models.Exam] = []
        for index in range(config.exam_count):
            exam = db.get(models.Exam, stable_id(config.batch_id, "exam", index))
            if exam is None or exam.org_id != org.id:
                raise RuntimeError(f"Không tìm thấy kỳ thi thứ {index + 1} của batch")
            start = exam.scheduled_start_at or exam.created_at
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            exam.name = exam_title(index, start)
            exam.exam_url = f"https://{config.exam_domain}/exams/{exam.join_code.lower()}"
            exam.google_allowed_domain = config.student_domain if exam.candidate_auth_mode == "google" else None
            exam.updated_at = utc_now()
            exams.append(exam)
            owner = db.get(models.User, exam.owner_user_id) if exam.owner_user_id else None
            exam_updates[exam.id] = {
                "exam_name": exam.name,
                "owner_email": owner.email if owner else "",
            }
            audit = db.get(models.AuditLog, stable_id(config.batch_id, "audit", f"exam-create:{index}"))
            if audit:
                audit.action = "exam.create"
                audit.reason = "Khởi tạo kỳ thi theo kế hoạch đào tạo"
                audit.after_json = json.dumps({"status": exam.status}, ensure_ascii=False)

        pool_size = max(50, min(config.session_count, (config.session_count // max(1, config.exam_count)) + 20))
        identities: list[models.CandidateIdentity] = []
        for index in range(pool_size):
            identity = db.get(models.CandidateIdentity, stable_id(config.batch_id, "candidate", index))
            if identity is None:
                raise RuntimeError(f"Không tìm thấy candidate identity thứ {index + 1}")
            display_name, _, email = student_identity(index, config.student_domain)
            identity.provider_subject = google_subject(config.batch_id, index)
            identity.email = email
            identity.display_name = display_name
            identity.hosted_domain = config.student_domain
            identity.updated_at = utc_now()
            identities.append(identity)

        eligible_exam_indices = active_exam_indices(exams)
        for index in range(config.session_count):
            session_id = stable_id(config.batch_id, "session", index)
            exam_index = eligible_exam_indices[index % len(eligible_exam_indices)]
            ordinal = index // len(eligible_exam_indices)
            student_name, candidate_number, student_email = student_identity(ordinal, config.student_domain)
            exam_session = db.get(models.ExamSession, session_id)
            if exam_session is None or exam_session.exam_id != exams[exam_index].id:
                raise RuntimeError(f"Không tìm thấy hoặc sai kỳ thi của phiên: {session_id}")
            identity = identities[ordinal % len(identities)] if exam_session.authentication_method == "google" else None
            candidate_email = identity.email if identity else student_email
            exam_session.student_name = student_name
            exam_session.candidate_number = candidate_number
            exam_session.candidate_email = candidate_email
            exam_session.candidate_identity_id = identity.id if identity else None
            session_updates[session_id] = {
                "exam_name": exams[exam_index].name,
                "student_name": student_name,
                "candidate_number": candidate_number,
                "candidate_email": candidate_email,
            }

            session_dir = config.sessions_root / session_id
            meta_path = session_dir / "session_meta.json"
            if not meta_path.is_file():
                raise RuntimeError(f"Phiên thiếu session_meta.json: {session_id}")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta.update({
                "student_name": student_name,
                "candidate_number": candidate_number,
                "candidate_email": candidate_email,
            })
            for key in ("synthetic", "batch_id", "risk_profile"):
                meta.pop(key, None)
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            violations_path = session_dir / "violations.jsonl"
            violations = _read_jsonl(violations_path)
            severity_by_snapshot: dict[str, str] = {}
            for violation in violations:
                violation["metadata"] = {
                    "fusion_config_version": str(violation.get("metadata", {}).get("fusion_config_version", "v1")),
                    "capture_source": "risk_fusion_engine",
                }
                snapshot_path = violation.get("snapshot_path")
                if snapshot_path:
                    severity_by_snapshot[Path(str(snapshot_path)).name] = str(violation.get("severity", "MEDIUM"))
            jsonl_write(violations_path, violations)

            browser_path = session_dir / "browser_events.jsonl"
            browser_events = _read_jsonl(browser_path)
            for event in browser_events:
                event["observed_origin"] = f"https://{config.exam_domain}"
                event["metadata"] = {"source": "browser_extension"}
            jsonl_write(browser_path, browser_events)

            snapshot_dir = session_dir / "snapshots"
            for filename, severity in severity_by_snapshot.items():
                target = snapshot_dir / filename
                if target.is_file():
                    target.write_bytes(snapshot_payloads.get(severity, snapshot_payloads["MEDIUM"]))
                    refreshed_snapshots += 1

        exam_ids = [exam.id for exam in exams]
        legacy_audits = db.query(models.AuditLog).filter(
            models.AuditLog.exam_id.in_(exam_ids),
            models.AuditLog.action == "exam.incident.review.synthetic",
        ).all()
        for audit in legacy_audits:
            audit.action = "exam.incident.review"
            audit.reason = "Cập nhật kết quả rà soát sự kiện"

        output_backup = refresh_output_files(
            config, database_backup, email_map, staff_by_email, exam_updates, session_updates
        )
        report_formats_by_session: dict[str, set[str]] = defaultdict(set)
        for report in manifest.get("reports", []):
            if report.get("format") in {"html", "pdf"}:
                report_formats_by_session[str(report["session_id"])].add(str(report["format"]))
        for session_id, formats in report_formats_by_session.items():
            generate_report(
                config.sessions_root / session_id,
                fusion_config_path=ROOT / "config" / "fusion.yaml",
                output_dir=config.sessions_root / session_id,
                formats=sorted(formats),
            )
        db.commit()

        counts = {
            "users": config.org_admins + config.managers + config.proctors,
            "exams": len(exams),
            "sessions": config.session_count,
            "snapshots": refreshed_snapshots,
            "legacy_audit_actions": db.query(models.AuditLog).filter(
                models.AuditLog.exam_id.in_(exam_ids),
                models.AuditLog.action.like("%.synthetic"),
            ).count(),
        }
    assert output_backup is not None
    return counts, database_backup, output_backup


def generate_sample_reports(
    db: Any,
    config: Config,
    stats: GenerationStats,
    requesters: list[models.User],
) -> None:
    if config.sample_reports <= 0 or not stats.sessions:
        return
    candidates = sorted(stats.sessions, key=lambda row: (row["violation_count"], row["risk_score_peak"]), reverse=True)
    selected = candidates[: min(config.sample_reports, len(candidates))]
    for index, row in enumerate(selected):
        session_dir = config.sessions_root / row["session_id"]
        try:
            paths = generate_report(
                session_dir,
                fusion_config_path=ROOT / "config" / "fusion.yaml",
                output_dir=session_dir,
                formats=list(config.report_formats),
            )
        except Exception as exc:  # Dataset remains useful even if optional PDF backend fails.
            stats.reports.append({"session_id": row["session_id"], "format": "error", "path": str(exc)})
            continue
        for fmt, path in paths.items():
            requester = requesters[index % len(requesters)]
            now = utc_now()
            db.add(models.ReportJob(
                id=stable_id(config.batch_id, "report-job", f"{row['session_id']}:{fmt}"),
                exam_session_id=row["session_id"],
                requested_by_user_id=requester.id,
                format=fmt,
                status="completed",
                output_path=str(path),
                created_at=now,
                started_at=now,
                completed_at=now,
                expires_at=now + timedelta(days=30),
            ))
            stats.report_jobs += 1
            stats.reports.append({"session_id": row["session_id"], "format": fmt, "path": str(path)})


def aggregate_rows(stats: GenerationStats) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    exam_lookup = {row["exam_id"]: row for row in stats.exams}
    exam_sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exam_violations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in stats.sessions:
        exam_sessions[row["exam_id"]].append(row)
    for row in stats.violations:
        exam_violations[row["exam_id"]].append(row)
    exam_summary: list[dict[str, Any]] = []
    for exam_id, exam in exam_lookup.items():
        sessions = exam_sessions[exam_id]
        violations = exam_violations[exam_id]
        profiles = Counter(row["risk_profile"] for row in sessions)
        exam_summary.append({
            "exam_id": exam_id,
            "exam_name": exam["exam_name"],
            "exam_status": exam["status"],
            "owner_email": exam["owner_email"],
            "session_count": len(sessions),
            "ended_sessions": sum(row["status"] == "ended" for row in sessions),
            "active_sessions": sum(row["status"] == "active" for row in sessions),
            "disconnected_sessions": sum(row["status"] == "disconnected" for row in sessions),
            "normal_profiles": profiles["normal"],
            "low_profiles": profiles["low"],
            "medium_profiles": profiles["medium"],
            "high_profiles": profiles["high"],
            "violation_count": len(violations),
            "high_violations": sum(row["severity"] == "HIGH" for row in violations),
            "confirmed_incidents": sum(row["review_status"] == "confirmed" for row in violations),
            "average_peak_risk": round(sum(row["risk_score_peak"] for row in sessions) / len(sessions), 2) if sessions else 0,
        })
    violation_counts = Counter((row["violation_type"], row["severity"], row["review_status"]) for row in stats.violations)
    violation_summary = [
        {"violation_type": key[0], "severity": key[1], "review_status": key[2], "count": count}
        for key, count in sorted(violation_counts.items())
    ]
    daily_counts: dict[str, dict[str, Any]] = {}
    for row in stats.sessions:
        day = row["started_at"][:10]
        item = daily_counts.setdefault(day, {"date": day, "sessions": 0, "violations": 0, "browser_events": 0, "high_risk_sessions": 0})
        item["sessions"] += 1
        item["violations"] += row["violation_count"]
        item["browser_events"] += row["browser_event_count"]
        item["high_risk_sessions"] += row["risk_profile"] == "high"
    return exam_summary, violation_summary, [daily_counts[key] for key in sorted(daily_counts)]


def write_outputs(config: Config, stats: GenerationStats, backup_path: Path | None) -> None:
    output_dir = config.output_root / config.batch_id
    if output_dir.exists():
        raise RuntimeError(f"Thư mục output đã tồn tại: {output_dir}")
    output_dir.mkdir(parents=True)
    csv_write(
        output_dir / "accounts.csv",
        ("email", "password", "display_name", "organization_role", "exam_role", "purpose"),
        stats.users,
    )
    csv_write(
        output_dir / "exams.csv",
        ("exam_id", "exam_name", "status", "owner_email", "candidate_auth_mode", "scheduled_start_at", "scheduled_end_at", "assignments"),
        stats.exams,
    )
    csv_write(
        output_dir / "sessions.csv",
        ("session_id", "exam_id", "exam_name", "student_name", "candidate_number", "candidate_email", "authentication_method", "client_type", "status", "risk_profile", "risk_score_peak", "integrity_score", "violation_count", "browser_event_count", "started_at", "ended_at", "duration_sec"),
        stats.sessions,
    )
    csv_write(
        output_dir / "violations.csv",
        ("exam_id", "session_id", "event_id", "student_name", "profile", "video_time_sec", "violation_type", "severity", "risk_score", "review_status", "timestamp"),
        stats.violations,
    )
    exam_summary, violation_summary, daily_summary = aggregate_rows(stats)
    csv_write(output_dir / "exam_summary.csv", tuple(exam_summary[0]) if exam_summary else ("exam_id",), exam_summary)
    csv_write(output_dir / "violation_summary.csv", ("violation_type", "severity", "review_status", "count"), violation_summary)
    csv_write(output_dir / "daily_summary.csv", ("date", "sessions", "violations", "browser_events", "high_risk_sessions"), daily_summary)
    csv_write(
        output_dir / "role_matrix.csv",
        ("role", "scope", "capabilities"),
        (
            {"role": "org_admin", "scope": "organization", "capabilities": "members, policy, audit; không tự động truy cập kỳ thi"},
            {"role": "owner", "scope": "assigned exam", "capabilities": "manage, assign, monitor, evidence, review, export"},
            {"role": "manager", "scope": "assigned exam", "capabilities": "manage, assign, monitor, evidence, review, export"},
            {"role": "proctor", "scope": "assigned exam", "capabilities": "monitor, end session, evidence, review, export"},
        ),
    )
    manifest = {
        "batch_id": config.batch_id,
        "generated_at": iso(utc_now()),
        "database_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
        "database_backup": str(backup_path) if backup_path else None,
        "organization": {"id": stats.organization_id, "name": stats.organization_name},
        "configuration": {
            "target_email": config.target_email,
            "exam_count": config.exam_count,
            "session_count": config.session_count,
            "days": config.days,
            "seed": config.seed,
            "org_admins": config.org_admins,
            "managers": config.managers,
            "proctors": config.proctors,
            "snapshot_rate": config.snapshot_rate,
            "sample_reports": config.sample_reports,
            "report_formats": config.report_formats,
        },
        "counts": {
            "users": len(stats.users),
            "exams": len(stats.exams),
            "sessions": len(stats.sessions),
            "violations": len(stats.violations),
            "browser_events": stats.browser_events,
            "incident_reviews": stats.incident_reviews,
            "snapshots": stats.snapshots,
            "report_jobs": stats.report_jobs,
        },
        "session_ids": stats.session_ids,
        "reports": stats.reports,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "README.md").write_text(
        f"""# Bộ dữ liệu báo cáo `{config.batch_id}`

- Tổ chức: **{stats.organization_name}**
- Tài khoản: **{len(stats.users)}** (`accounts.csv`)
- Kỳ thi: **{len(stats.exams)}**
- Phiên thi: **{len(stats.sessions)}**
- Vi phạm CV: **{len(stats.violations)}**
- Sự kiện trình duyệt: **{stats.browser_events}**
- Incident review đã lưu: **{stats.incident_reviews}**

Các file `exam_summary.csv`, `daily_summary.csv` và `violation_summary.csv` có
thể nhập trực tiếp vào Excel/Google Sheets để dựng bảng và biểu đồ báo cáo.
`sessions.csv` và `violations.csv` chứa dữ liệu chi tiết. Tất cả ứng viên,
email, snapshot và sự kiện trong batch đều là dữ liệu tổng hợp.

Tài khoản `org_admin` quản trị tenant nhưng không tự động xem kỳ thi. Dùng tài
khoản `manager` hoặc `proctor` trong `accounts.csv` để kiểm tra dashboard kỳ
thi theo đúng phạm vi phân công.
""",
        encoding="utf-8",
    )


def validate_dataset(db: Any, config: Config, stats: GenerationStats) -> dict[str, int]:
    user_ids = [stable_id(config.batch_id, "user", f"{group}:{index + 1}") for group, count in (
        ("org_admin", config.org_admins), ("manager", config.managers), ("proctor", config.proctors)
    ) for index in range(count)]
    exam_ids = [stable_id(config.batch_id, "exam", index) for index in range(config.exam_count)]
    counts = {
        "users": db.query(models.User).filter(models.User.id.in_(user_ids)).count(),
        "memberships": db.query(models.OrganizationMembership).filter(models.OrganizationMembership.user_id.in_(user_ids)).count(),
        "exams": db.query(models.Exam).filter(models.Exam.id.in_(exam_ids)).count(),
        "assignments": db.query(models.ExamAssignment).filter(models.ExamAssignment.exam_id.in_(exam_ids)).count(),
        "sessions": db.query(models.ExamSession).filter(models.ExamSession.id.in_(stats.session_ids)).count(),
        "reviews": db.query(models.IncidentReview).filter(models.IncidentReview.exam_session_id.in_(stats.session_ids)).count(),
    }
    expected = {
        "users": len(user_ids), "memberships": len(user_ids), "exams": config.exam_count,
        "sessions": config.session_count, "reviews": stats.incident_reviews,
    }
    for name, expected_count in expected.items():
        if counts[name] != expected_count:
            raise RuntimeError(f"Kiểm tra {name} thất bại: {counts[name]} != {expected_count}")
    if counts["assignments"] < config.exam_count * 3:
        raise RuntimeError("Mỗi kỳ thi phải có ít nhất owner, manager và proctor")
    required = {
        "session_meta.json", "signals.jsonl", "state_transitions.jsonl",
        "violations.jsonl", "browser_events.jsonl", "risk_score_timeline.jsonl",
    }
    parsed_violations = 0
    for session_id in stats.session_ids:
        session_dir = config.sessions_root / session_id
        missing = [name for name in required if not (session_dir / name).is_file()]
        if missing:
            raise RuntimeError(f"Phiên {session_id} thiếu file: {missing}")
        meta = json.loads((session_dir / "session_meta.json").read_text(encoding="utf-8"))
        if meta.get("session_id") != session_id:
            raise RuntimeError(f"Metadata phiên không hợp lệ: {session_id}")
        parsed_violations += len(_read_jsonl(session_dir / "violations.jsonl"))
        _read_jsonl(session_dir / "browser_events.jsonl")
        _read_jsonl(session_dir / "risk_score_timeline.jsonl")
    if parsed_violations != len(stats.violations):
        raise RuntimeError(f"Số violation JSONL sai: {parsed_violations} != {len(stats.violations)}")
    return counts


def backup_sqlite_database(batch_id: str) -> Path | None:
    if not DATABASE_URL.startswith("sqlite"):
        return None
    database = engine.url.database
    if not database or database == ":memory:":
        return None
    source = Path(database)
    if not source.is_absolute():
        source = (ROOT / source).resolve()
    if not source.is_file():
        return None
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    destination = source.with_name(f"{source.name}-seed-backup-{batch_id}-{stamp}")
    shutil.copy2(source, destination)
    return destination


def remove_partial_session_dirs(config: Config, session_ids: Sequence[str]) -> None:
    root = config.sessions_root.resolve()
    for session_id in session_ids:
        target = (config.sessions_root / session_id).resolve()
        if target.parent == root and target.name == session_id and target.is_dir():
            shutil.rmtree(target)


def generate(config: Config) -> tuple[GenerationStats, Path | None, dict[str, int]]:
    config.sessions_root.mkdir(parents=True, exist_ok=True)
    if (config.output_root / config.batch_id).exists():
        raise RuntimeError(f"Batch output đã tồn tại: {config.output_root / config.batch_id}")
    Base.metadata.create_all(bind=engine)
    apply_additive_migrations(engine)
    backup_path = backup_sqlite_database(config.batch_id)
    stats = GenerationStats()
    now = utc_now()
    with SessionLocal() as db:
        try:
            target_user = db.query(models.User).filter(models.User.email == config.target_email).first()
            if target_user is None:
                raise RuntimeError(f"Không tìm thấy tài khoản mục tiêu: {config.target_email}")
            membership = db.query(models.OrganizationMembership).filter_by(
                user_id=target_user.id, org_id=target_user.org_id, status="active"
            ).first()
            if membership is None:
                raise RuntimeError("Tài khoản mục tiêu không có membership hoạt động")
            org = db.get(models.Organization, membership.org_id)
            if org is None:
                raise RuntimeError("Không tìm thấy tổ chức của tài khoản mục tiêu")
            stats.organization_id = org.id
            stats.organization_name = org.name
            shared_hash = hash_password(config.password)
            _, managers, proctors, stats.users = create_users(
                db, config, org, target_user.id, shared_hash
            )
            exams, stats.exams = create_exams_and_assignments(
                db, config, org, managers, proctors, now
            )
            identities = create_candidate_identities(db, config, now)
            create_sessions(db, config, org, exams, identities, managers, proctors, now, stats)
            db.flush()
            generate_sample_reports(db, config, stats, managers + proctors)
            db.flush()
            validation = validate_dataset(db, config, stats)
            write_outputs(config, stats, backup_path)
            db.commit()
            return stats, backup_path, validation
        except Exception:
            db.rollback()
            remove_partial_session_dirs(config, stats.session_ids)
            output_dir = config.output_root / config.batch_id
            if output_dir.is_dir() and output_dir.resolve().parent == config.output_root.resolve():
                shutil.rmtree(output_dir)
            raise


def dry_run(config: Config) -> None:
    with SessionLocal() as db:
        user = db.query(models.User).filter(models.User.email == config.target_email).first()
        if user is None:
            raise RuntimeError(f"Không tìm thấy tài khoản mục tiêu: {config.target_email}")
        org = db.get(models.Organization, user.org_id)
        if org is None:
            raise RuntimeError("Không tìm thấy tổ chức của tài khoản mục tiêu")
        print(f"[DRY-RUN] Tổ chức: {org.name} ({org.id})")
    estimated_violations = int(config.session_count * sum(
        weight * ((VIOLATION_RANGES[name][0] + VIOLATION_RANGES[name][1]) / 2)
        for name, weight in PROFILE_WEIGHTS
    ))
    print(f"[DRY-RUN] {config.org_admins} org_admin, {config.managers} manager, {config.proctors} proctor")
    print(f"[DRY-RUN] {config.exam_count} kỳ thi, {config.session_count} phiên, ~{estimated_violations} violations")
    print(f"[DRY-RUN] Sessions: {config.sessions_root}")
    print(f"[DRY-RUN] Báo cáo tổng hợp: {config.output_root / config.batch_id}")


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="Sinh dữ liệu lớn cho dashboard/báo cáo DATT")
    parser.add_argument("--batch-id", type=sanitize_batch_id, default="report-2026")
    parser.add_argument("--target-email", default="test@gmail.com", help="Tài khoản xác định tổ chức đích")
    parser.add_argument("--exam-count", type=int, default=10)
    parser.add_argument("--session-count", type=int, default=1000)
    parser.add_argument("--days", type=int, default=180, help="Khoảng lịch sử dữ liệu")
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument("--org-admins", type=int, default=2)
    parser.add_argument("--managers", type=int, default=3)
    parser.add_argument("--proctors", type=int, default=4)
    parser.add_argument("--snapshot-rate", type=float, default=0.05)
    parser.add_argument("--sample-reports", type=int, default=3)
    parser.add_argument("--report-formats", default="html,pdf")
    parser.add_argument("--sessions-root", type=Path, default=Path(os.environ.get("SESSIONS_ROOT", ROOT / "sessions")))
    parser.add_argument("--output-root", type=Path, default=ROOT / "generated_reports")
    parser.add_argument("--staff-domain", default="phenikaa.edu.vn")
    parser.add_argument("--student-domain", default="st.phenikaa.edu.vn")
    parser.add_argument("--exam-domain", default="lms.phenikaa.edu.vn")
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Cập nhật tên/email/URL/audit/evidence của batch hiện có mà không đổi ID và số lượng",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.exam_count < 3 or args.session_count < 1 or args.days < 1:
        parser.error("exam-count >= 3, session-count >= 1 và days >= 1")
    if args.org_admins < 1 or args.managers < 2 or args.proctors < 1:
        parser.error("cần ít nhất 1 org_admin, 2 manager và 1 proctor")
    if not 0.0 <= args.snapshot_rate <= 1.0:
        parser.error("snapshot-rate phải nằm trong [0, 1]")
    if args.sample_reports < 0:
        parser.error("sample-reports không được âm")
    formats = tuple(item.strip().lower() for item in args.report_formats.split(",") if item.strip())
    if not formats or set(formats) - {"html", "pdf"}:
        parser.error("report-formats chỉ nhận html,pdf")
    domain_pattern = re.compile(r"(?=^.{3,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
    for label, value in (
        ("staff-domain", args.staff_domain),
        ("student-domain", args.student_domain),
        ("exam-domain", args.exam_domain),
    ):
        if not domain_pattern.fullmatch(value.strip().lower()):
            parser.error(f"{label} không hợp lệ")
    password = os.environ.get("REPORT_DATA_PASSWORD") or f"Demo-{secrets.token_urlsafe(12)}"
    if len(password) < 12 or len(password.encode("utf-8")) > 72:
        parser.error("REPORT_DATA_PASSWORD phải dài 12-72 byte UTF-8")
    return Config(
        batch_id=args.batch_id,
        target_email=args.target_email.strip().casefold(),
        exam_count=args.exam_count,
        session_count=args.session_count,
        days=args.days,
        seed=args.seed,
        org_admins=args.org_admins,
        managers=args.managers,
        proctors=args.proctors,
        snapshot_rate=args.snapshot_rate,
        sample_reports=args.sample_reports,
        report_formats=formats,
        sessions_root=args.sessions_root.resolve(),
        output_root=args.output_root.resolve(),
        password=password,
        dry_run=args.dry_run,
        staff_domain=args.staff_domain.strip().lower(),
        student_domain=args.student_domain.strip().lower(),
        exam_domain=args.exam_domain.strip().lower(),
        refresh_existing=args.refresh_existing,
    )


def main() -> None:
    config = parse_args()
    if config.dry_run:
        dry_run(config)
        return
    if config.refresh_existing:
        counts, database_backup, output_backup = refresh_existing_dataset(config)
        print(f"Đã cập nhật dữ liệu hiển thị của batch: {config.batch_id}")
        print(f"Kết quả: {counts}")
        if database_backup:
            print(f"Database backup: {database_backup}")
        print(f"Output backup: {output_backup}")
        return
    stats, backup_path, validation = generate(config)
    print(f"Hoàn tất batch: {config.batch_id}")
    print(f"Tổ chức: {stats.organization_name}")
    print(f"Tài khoản: {len(stats.users)}; kỳ thi: {len(stats.exams)}; phiên: {len(stats.sessions)}")
    print(f"Violations: {len(stats.violations)}; browser events: {stats.browser_events}; reviews: {stats.incident_reviews}")
    print(f"Snapshots: {stats.snapshots}; report jobs: {stats.report_jobs}")
    print(f"Validation: {validation}")
    if backup_path:
        print(f"Database backup: {backup_path}")
    print(f"Tài khoản và CSV báo cáo: {config.output_root / config.batch_id}")


if __name__ == "__main__":
    main()
