"""Mô phỏng 1 phiên giám sát ~20 phút để demo module báo cáo (Tuần 11) khi
KHÔNG có webcam thật sẵn sàng (VD môi trường dev không có camera). Dùng
CHÍNH `RiskFusionEngine.from_config` thật (Tuần 10, đọc `config/fusion.yaml`
y hệt `main.py`) nạp 1 chuỗi `SignalResult` giả lập theo kịch bản hành vi
hỗn hợp — KHÔNG tự tay viết `violations.jsonl` giả, để log sinh ra đúng
logic thật của Risk Fusion Engine, chỉ khác nguồn tín hiệu đầu vào (giả lập
thay vì webcam thật).

Kịch bản (giống HUONG_DAN_DEMO_TUAN8.md tinh thần "hành vi hỗn hợp"):
  0-2   phút : bình thường
  2-3   phút : dùng điện thoại liên tục (OBJECT_PRESENCE) -> vi phạm MEDIUM
  5-7   phút : vừa nhìn ra ngoài (EYE_STATE) vừa nói chuyện (MOUTH_STATE) và
               quay đầu (HEAD_POSE) cùng lúc -> 3 tín hiệu yếu cộng dồn ->
               vi phạm MEDIUM (minh hoạ đúng thiết kế Tuần 10: 1 tín hiệu
               yếu một mình không đủ, nhiều tín hiệu cùng lúc thì đủ)
  10-11 phút : có người thứ 2 xuất hiện thoáng qua (MULTI_FACE) -> chỉ lên
               SUSPICIOUS/ALERT riêng lẻ, KHÔNG đủ vượt T_enter một mình
  15-17 phút : nghi thi hộ (IDENTITY mismatch) -> vi phạm MEDIUM
  18-19 phút : vừa nghi thi hộ VỪA dùng điện thoại cùng lúc -> vi phạm HIGH

Chạy: python scripts/simulate_demo_session.py
Sinh ra sessions/session_demo_simulated/ với đủ log + report.html/report.pdf.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fusion.engine import RiskFusionEngine
from src.fusion.risk_score_logger import RiskScoreLogger
from src.fusion.state_transition_logger import StateTransitionLogger
from src.reporting.report_generator import generate_report
from src.signals.base import SignalResult

SESSION_ID = "session_demo_simulated"
SESSIONS_DIR = Path("sessions")
FUSION_CONFIG_PATH = "config/fusion.yaml"
DURATION_SEC = 20 * 60


def _synthetic_frame(label: str) -> np.ndarray:
    frame = np.full((240, 320, 3), 40, dtype=np.uint8)
    cv2.putText(frame, "SNAPSHOT MO PHONG", (14, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, label, (14, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return frame


def _active_signals_at(t: float) -> dict:
    """Trả về dict signal_name -> exceeds_threshold (bool) tại thời điểm t
    (giây) theo kịch bản mô tả ở docstring module."""
    minute = t / 60.0
    active = {name: False for name in (
        "FACE_PRESENCE", "MULTI_FACE", "EYE_STATE", "MOUTH_STATE",
        "OBJECT_PRESENCE", "HEAD_POSE", "IDENTITY",
    )}

    if 2.0 <= minute < 3.0:
        active["OBJECT_PRESENCE"] = True
    if 5.0 <= minute < 7.0:
        active["EYE_STATE"] = True
        active["MOUTH_STATE"] = True
        active["HEAD_POSE"] = True
    if 10.0 <= minute < 11.0:
        active["MULTI_FACE"] = True
    if 15.0 <= minute < 17.0:
        active["IDENTITY"] = True
    if 18.0 <= minute < 19.0:
        active["IDENTITY"] = True
        active["OBJECT_PRESENCE"] = True

    return active


def main() -> None:
    session_dir = SESSIONS_DIR / SESSION_ID
    snapshot_dir = session_dir / "snapshots"
    session_dir.mkdir(parents=True, exist_ok=True)

    state_logger = StateTransitionLogger(session_dir / "state_transitions.jsonl")
    risk_score_logger = RiskScoreLogger(session_dir / "risk_score_timeline.jsonl")
    engine = RiskFusionEngine.from_config(
        FUSION_CONFIG_PATH, session_id=SESSION_ID, session_start_ts=0.0,
        snapshot_dir=snapshot_dir, logger=state_logger, risk_score_logger=risk_score_logger,
    )

    violations_path = session_dir / "violations.jsonl"
    violation_count = 0
    with open(violations_path, "w", encoding="utf-8") as violations_file:
        for t in range(0, DURATION_SEC + 1):
            active = _active_signals_at(float(t))
            results = [
                SignalResult(
                    signal_name=name, timestamp=float(t),
                    value=1.0 if exceeds else 0.0, exceeds_threshold=exceeds, confidence=1.0,
                )
                for name, exceeds in active.items()
            ]
            frame = _synthetic_frame(f"t={t}s") if any(active.values()) else None
            event = engine.update(results, frame_bgr=frame)
            if event is not None:
                violation_count += 1
                violations_file.write(json.dumps(dataclasses.asdict(event), ensure_ascii=False) + "\n")
                print(f"[t={t}s] Violation #{violation_count}: {event.severity} - {event.primary_violation} "
                      f"(risk_score={event.risk_score})")

    state_logger.close()
    risk_score_logger.close()

    started_at = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone(timedelta(hours=7)))
    ended_at = started_at + timedelta(seconds=DURATION_SEC)
    meta = {
        "session_id": SESSION_ID,
        "started_at": started_at.isoformat(timespec="seconds"),
        "ended_at": ended_at.isoformat(timespec="seconds"),
        "duration_sec": float(DURATION_SEC),
        "fusion_config_version": "v1",
        "fps_avg": 15.0,
    }
    (session_dir / "session_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nDa mo phong xong: {violation_count} violation(s), phien luu tai {session_dir}")
    print("Dang sinh bao cao...")
    paths = generate_report(session_dir, fusion_config_path=FUSION_CONFIG_PATH)
    print(f"HTML: {paths['html']}")
    print(f"PDF : {paths['pdf']}")


if __name__ == "__main__":
    main()
