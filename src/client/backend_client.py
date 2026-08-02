"""BackendClient - client-side ket noi toi backend platform (Tuan 12 moi,
xem docs/KE_HOACH_PLATFORM.md). 2 viec: (1) `join_exam()` - 1 loi goi REST
chan ngan lay session_token bang join_code + ten; (2) gui SignalResult/
ViolationEvent/risk_score qua WebSocket CHAY NEN (1 thread rieng, dung
`websockets.sync.client` - khong can asyncio, giu code don gian/dong bo cung
phong cach voi vong lap webcam chinh trong main.py), khong lam cham vong lap
xu ly frame.

Thiet ke "offline-first" (docs/KE_HOACH_PLATFORM.md muc 1): neu backend
khong the ket noi (VD chua chay docker compose, hoac backend.enabled=false
trong config/fusion.yaml), moi ham send_* la no-op an toan - vong lap giam
sat cuc bo (ghi JSONL local, sinh bao cao local) hoat dong DUNG Y HET nhu
khong co backend, khong raise/crash, khong retry moi frame gay tran log.
"""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

import httpx
from websockets.exceptions import WebSocketException
from websockets.sync.client import ClientConnection, connect as ws_connect

from src.fusion.violation_event import ViolationEvent
from src.signals.base import SignalResult

_QUEUE_MAXSIZE = 1000
_CONNECT_TIMEOUT_SEC = 5.0
_HEARTBEAT_INTERVAL_SEC = 5.0
_MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class JoinResult:
    session_token: str
    session_id: str
    exam_name: str


def join_exam(
    base_url: str,
    join_code: str,
    student_name: str,
    timeout_sec: float = 5.0,
    client: Optional[httpx.Client] = None,
) -> Optional[JoinResult]:
    """1 loi goi REST chan ngan (`POST /exams/join`) - tra ve `None` neu ma
    khong hop le/backend khong phan hoi (khong raise, de `AppController` tu
    hien thi thong bao loi thay vi lam crash ung dung).

    `client` co the truyen vao de test (VD `httpx.Client(transport=
    httpx.MockTransport(...))`) ma khong can mo cong TCP that - mac dinh
    (`None`) tu tao 1 `httpx.Client` tam thoi cho dung goi nay."""
    request_kwargs = dict(
        url=f"{base_url.rstrip('/')}/exams/join",
        json={"join_code": join_code, "student_name": student_name},
        timeout=timeout_sec,
    )
    try:
        if client is not None:
            response = client.post(**request_kwargs)
        else:
            with httpx.Client() as temp_client:
                response = temp_client.post(**request_kwargs)
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    body = response.json()
    return JoinResult(
        session_token=body["session_token"], session_id=body["session_id"], exam_name=body["exam_name"],
    )


class BackendClient:
    """1 instance/phien giam sat. `connect()` thu ket noi ĐÚNG 1 LẦN - neu
    that bai, tu vo hieu hoa vinh vien cho phien nay (khong retry moi frame,
    tranh tran log/lam cham vong lap khi backend khong chay)."""

    def __init__(self, ws_url: str, session_token: str) -> None:
        self._url = f"{ws_url.rstrip('/')}/ws/client"
        self._session_token = session_token
        self._queue: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._thread: Optional[threading.Thread] = None
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def connect(self) -> bool:
        """Thu ket noi dong bo 1 lan (block toi da `_CONNECT_TIMEOUT_SEC`
        giay) de biet ngay thanh cong hay khong, roi giao phan gui con lai
        cho thread nen. Tra ve `False` neu that bai."""
        try:
            connection = ws_connect(
                self._url,
                open_timeout=_CONNECT_TIMEOUT_SEC,
                additional_headers={"Authorization": f"Bearer {self._session_token}"},
            )
        except (WebSocketException, OSError, TimeoutError):
            self._enabled = False
            return False

        self._enabled = True
        self._thread = threading.Thread(target=self._run, args=(connection,), daemon=True)
        self._thread.start()
        return True

    def _run(self, connection: ClientConnection) -> None:
        with connection:
            while True:
                try:
                    message = self._queue.get(timeout=_HEARTBEAT_INTERVAL_SEC)
                except queue.Empty:
                    message = {"type": "heartbeat", "data": {"timestamp": time.time()}}
                if message is None:  # sentinel tu close() - dong ket noi
                    return
                try:
                    connection.send(json.dumps(message, ensure_ascii=False))
                except (TypeError, ValueError):
                    # One malformed local metadata value must not stop all
                    # subsequent heartbeats/telemetry for the session.
                    continue
                except (WebSocketException, OSError):
                    # Mat ket noi giua chung - dung gui tiep nhung KHONG lam
                    # crash vong lap chinh (offline-first, xem docstring module).
                    self._enabled = False
                    return

    def _enqueue(self, message: Dict[str, Any]) -> None:
        if not self._enabled:
            return
        try:
            self._queue.put_nowait(message)
        except queue.Full:
            # Backend cham/mat ket noi ma chua kip phat hien - bo qua message
            # moi nhat thay vi chan vong lap frame chinh de cho hang doi voi.
            pass

    @staticmethod
    def _snapshot_payload(snapshot_path: Optional[str]) -> Optional[Dict[str, str]]:
        if not snapshot_path:
            return None
        path = Path(snapshot_path)
        suffix = path.suffix.lower()
        content_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(suffix)
        if content_type is None:
            return None
        try:
            size = path.stat().st_size
            if size <= 0 or size > _MAX_SNAPSHOT_BYTES:
                return None
            raw = path.read_bytes()
        except OSError:
            return None
        if content_type == "image/jpeg" and not raw.startswith(b"\xff\xd8\xff"):
            return None
        if content_type == "image/png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return None
        return {
            "content_type": content_type,
            "data_base64": base64.b64encode(raw).decode("ascii"),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def send_violation_event(self, event: ViolationEvent) -> None:
        data = dataclasses.asdict(event)
        data["snapshot"] = self._snapshot_payload(event.snapshot_path)
        # Local filesystem paths are never sent to or trusted by the server.
        data["snapshot_path"] = None
        self._enqueue({"type": "violation_event", "data": data})

    def send_telemetry_update(
        self,
        results: Iterable[SignalResult],
        signal_states: Mapping[str, str],
        risk_score: float,
        session_state: str,
        video_time_sec: float,
        timestamp: float,
    ) -> None:
        self._enqueue(
            {
                "type": "telemetry_update",
                "data": {
                    "risk_score": risk_score,
                    "session_state": session_state,
                    "video_time_sec": video_time_sec,
                    "timestamp": timestamp,
                    "signals": [dataclasses.asdict(result) for result in results],
                    "signal_states": dict(signal_states),
                },
            }
        )

    def send_end_session(self, reason: str = "completed") -> None:
        self._enqueue({"type": "end_session", "data": {"reason": reason}})

    def close(self) -> None:
        if not self._enabled or self._thread is None:
            return
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(None)
            except (queue.Empty, queue.Full):
                pass
        self._thread.join(timeout=_CONNECT_TIMEOUT_SEC)
        self._enabled = False
