"""RiskScoreLogger — ghi `risk_score` tổng hợp MỖI FRAME ra JSONL, phục vụ
vẽ biểu đồ "risk score theo thời gian" ở module báo cáo (Tuần 11,
`src/reporting/`).

Khác `StateTransitionLogger` (chỉ ghi lúc trạng thái ĐỔI, tránh phình log) —
ở đây cố ý ghi MỌI frame vì mục đích khác: dựng đường cong risk_score liên
tục theo thời gian cho báo cáo cuối phiên, không phải log debug real-time.
Số dòng tối đa = số frame của cả phiên (VD phiên 30 phút ở 15 FPS ≈ 27,000
dòng JSONL nhỏ) — chấp nhận được, không dùng nếu cần log vô hạn/streaming dài
hơn nhiều (ngoài phạm vi đồ án)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union


class RiskScoreLogger:
    def __init__(self, log_path: Union[str, Path]) -> None:
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "a", encoding="utf-8")

    def log(self, timestamp: float, video_time_sec: float, risk_score: float, session_state: str) -> None:
        record = {
            "timestamp": timestamp,
            "video_time_sec": round(video_time_sec, 3),
            "risk_score": round(risk_score, 3),
            "session_state": session_state,
        }
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def __enter__(self) -> "RiskScoreLogger":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
