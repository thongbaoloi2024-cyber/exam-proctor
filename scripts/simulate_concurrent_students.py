"""Mo phong NHIEU thi sinh giam sat dong thoi qua 1 backend dang chay that
(Tuan 15 - "demo thu 2-3 phien dong thoi", xem KE_HOACH_4_THANG_THEO_TUAN.md
va docs/KE_HOACH_PLATFORM.md).

Khac `scripts/simulate_demo_session.py` (mo phong 1 phien, KHONG can backend,
chi kiem tra RiskFusionEngine + bao cao cuc bo) - script nay ket noi qua
HTTP/WebSocket THAT toi 1 backend dang chay (docker compose hoac uvicorn cuc
bo), dung de tu kiem tra dashboard hoat dong dung TRUOC khi demo that truoc
hoi dong (khong phai script tu dong hoa buoi demo - do la lam bang tay qua
trinh duyet that).

Chay:
    1. Bat backend that:
         docker compose up --build
       (hoac uvicorn backend.main:app --port 8000 tu venv co san neu khong
       dung Docker).
    2. python scripts/simulate_concurrent_students.py
    3. Mo trinh duyet toi dia chi duoc script in ra, dang nhap bang tai
       khoan duoc in ra, mo dashboard cua ky thi vua tao - quan sat cac hang
       cap nhat real-time trong luc script con dang chay (mac dinh 30 giay).

Tham so tuy chinh: --base-url, --num-students, --duration-sec.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Tuple

import httpx
from websockets.sync.client import connect

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_BASE_URL = "http://localhost:8000"
_SIGNAL_NAMES = (
    "FACE_PRESENCE", "MULTI_FACE", "EYE_STATE", "MOUTH_STATE",
    "OBJECT_PRESENCE", "HEAD_POSE", "IDENTITY",
)
_WEIGHTS = {
    "FACE_PRESENCE": 2.0, "MULTI_FACE": 2.0, "EYE_STATE": 1.0,
    "MOUTH_STATE": 1.0, "OBJECT_PRESENCE": 2.5, "HEAD_POSE": 1.0,
    "IDENTITY": 3.0,
}
_VIOLATION = {
    "EYE_STATE": "EYES_CLOSED", "MOUTH_STATE": "TALKING",
    "HEAD_POSE": "HEAD_POSE_AWAY", "OBJECT_PRESENCE": "OBJECT_DETECTED",
    "IDENTITY": "IDENTITY_MISMATCH",
}


def _ws_url(base_url: str) -> str:
    return base_url.replace("http://", "ws://").replace("https://", "wss://")


def register_demo_admin(base_url: str) -> Tuple[str, str]:
    email = f"demo-{uuid.uuid4().hex[:8]}@simulate.local"
    password = "matkhau123"
    resp = httpx.post(
        f"{base_url}/auth/register",
        json={"organization_name": "To chuc Demo Dong Thoi", "admin_email": email, "admin_password": password},
    )
    resp.raise_for_status()
    return resp.json()["access_token"], email


def create_demo_exam(base_url: str, admin_token: str) -> dict:
    resp = httpx.post(
        f"{base_url}/exams", json={"name": "Ky thi mo phong dong thoi"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp.raise_for_status()
    return resp.json()


def student_worker(
    base_url: str, join_code: str, student_index: int, duration_sec: float, stop_event: threading.Event,
) -> None:
    """Moi thi sinh co xac suat "vi pham" khac nhau (0%/15%/40% xoay vong) -
    de dashboard nhin da dang hon la moi nguoi giong het nhau."""
    student_name = f"Thi sinh mo phong {student_index}"
    joined = httpx.post(
        f"{base_url}/exams/join", json={"join_code": join_code, "student_name": student_name},
    ).json()
    session_token = joined["session_token"]
    alert_probability = [0.0, 0.15, 0.4][student_index % 3]

    start = time.monotonic()
    was_alert = False
    with connect(
        f"{_ws_url(base_url)}/ws/client",
        additional_headers={"Authorization": f"Bearer {session_token}"},
    ) as ws:
        while time.monotonic() - start < duration_sec and not stop_event.is_set():
            elapsed = time.monotonic() - start
            is_alert = random.random() < alert_probability
            states = {name: "NORMAL" for name in _SIGNAL_NAMES}
            if is_alert:
                scenario = random.choice([
                    {"IDENTITY": "ALERT"},
                    {"OBJECT_PRESENCE": "ALERT"},
                    {"EYE_STATE": "ALERT", "MOUTH_STATE": "ALERT", "HEAD_POSE": "ALERT"},
                ])
                states.update(scenario)
            risk_score = sum(
                _WEIGHTS[name] * {"NORMAL": 0, "SUSPICIOUS": 1, "ALERT": 2}[state]
                for name, state in states.items()
            )
            session_state = "SESSION_ALERT" if is_alert else "SESSION_NORMAL"

            ws.send(json.dumps({
                "type": "telemetry_update",
                "data": {
                    "risk_score": risk_score, "session_state": session_state,
                    "video_time_sec": elapsed, "timestamp": time.time(),
                    "signals": [
                        {
                            "signal_name": name, "timestamp": time.time(),
                            "value": 1.0 if states[name] != "NORMAL" else 0.0,
                            "exceeds_threshold": states[name] != "NORMAL",
                            "confidence": 1.0, "metadata": {},
                        }
                        for name in _SIGNAL_NAMES
                    ],
                    "signal_states": states,
                },
            }))

            if is_alert and not was_alert:
                active_names = [name for name in _SIGNAL_NAMES if states[name] != "NORMAL"]
                primary_signal = max(
                    active_names,
                    key=lambda name: _WEIGHTS[name] * {"SUSPICIOUS": 1, "ALERT": 2}[states[name]],
                )
                ws.send(json.dumps({
                    "type": "violation_event",
                    "data": {
                        "event_id": str(uuid.uuid4()), "session_id": joined["session_id"],
                        "video_time_sec": elapsed, "timestamp": datetime.now(timezone.utc).isoformat(),
                        "risk_score": risk_score, "severity": "MEDIUM",
                        "primary_violation": _VIOLATION[primary_signal],
                        "contributing_signals": [
                            {
                                "signal_name": name, "violation_type": _VIOLATION[name],
                                "state": states[name], "value": 1.0, "weight": _WEIGHTS[name],
                            }
                            for name in active_names
                        ],
                        "snapshot_path": None, "metadata": {},
                    },
                }))
            was_alert = is_alert
            time.sleep(1.0)

        ws.send(json.dumps({"type": "end_session", "data": {}}))
    print(f"[{student_name}] da ket thuc phien.")


def dashboard_listener(
    base_url: str, admin_token: str, exam_id: str, duration_sec: float, stop_event: threading.Event,
) -> None:
    url = f"{_ws_url(base_url)}/ws/dashboard/{exam_id}"
    start = time.monotonic()
    with connect(url, additional_headers={"Authorization": f"Bearer {admin_token}"}) as ws:
        ws.socket.settimeout(1.0)
        while time.monotonic() - start < duration_sec + 3 and not stop_event.is_set():
            try:
                message = json.loads(ws.recv())
            except Exception:
                continue
            print(f"[DASHBOARD] {message['student_name']}: {message['type']} -> {message.get('data')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--num-students", type=int, default=3)
    parser.add_argument("--duration-sec", type=float, default=30.0)
    args = parser.parse_args()

    print(f"Dang ket noi backend tai {args.base_url} ...")
    admin_token, admin_email = register_demo_admin(args.base_url)
    exam = create_demo_exam(args.base_url, admin_token)

    print(f"Da tao to chuc demo - dang nhap bang: {admin_email} / matkhau123")
    print(f"Ky thi: '{exam['name']}' (join_code={exam['join_code']})")
    print(f"Mo trinh duyet: {args.base_url}/ui/exams/{exam['id']}/dashboard")
    print(f"Bat dau mo phong {args.num_students} thi sinh trong {args.duration_sec:.0f} giay...\n")

    stop_event = threading.Event()
    threads = [
        threading.Thread(
            target=dashboard_listener,
            args=(args.base_url, admin_token, exam["id"], args.duration_sec, stop_event),
            daemon=True,
        ),
    ]
    threads += [
        threading.Thread(
            target=student_worker,
            args=(args.base_url, exam["join_code"], i, args.duration_sec, stop_event),
            daemon=True,
        )
        for i in range(args.num_students)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=args.duration_sec + 10)

    print("\nHoan tat mo phong.")


if __name__ == "__main__":
    main()
