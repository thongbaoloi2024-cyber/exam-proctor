"""`ViolationEvent` — output của Risk Fusion Engine (Tuần 10), đúng schema
docs/DATA_SCHEMAS.md mục 3. Sinh ra tại **rising edge** của `SessionState`
(SESSION_NORMAL -> SESSION_ALERT, xem `session.py`).

`contributing_signals` là MẢNG (không phải 1 giá trị) — khác bản tham khảo
(chỉ ghi 1 loại vi phạm/frame theo if/elif ưu tiên): ghi lại TẤT CẢ signal
đang SUSPICIOUS/ALERT tại thời điểm sinh event, không chỉ 1 cái.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Enum violation_type <-> signal_name, đúng bảng mục 1.2 DATA_SCHEMAS.md -
# dùng chung 1 bộ tên để SignalResult, ViolationEvent, và ground-truth
# labeling (Tuần 13) không bị lệch tên giữa các module.
VIOLATION_TYPE_BY_SIGNAL: Dict[str, str] = {
    "FACE_PRESENCE": "FACE_ABSENT",
    "MULTI_FACE": "MULTIPLE_FACES",
    "EYE_STATE": "EYES_CLOSED",
    "MOUTH_STATE": "TALKING",
    "OBJECT_PRESENCE": "OBJECT_DETECTED",
    "HEAD_POSE": "HEAD_POSE_AWAY",
    "IDENTITY": "IDENTITY_MISMATCH",
}


@dataclass(frozen=True)
class ContributingSignal:
    """1 phần tử trong `contributing_signals` — 1 signal đang SUSPICIOUS/
    ALERT tại thời điểm sinh `ViolationEvent`."""

    signal_name: str
    violation_type: str
    state: str  # "SUSPICIOUS" | "ALERT"
    value: float
    weight: float


@dataclass(frozen=True)
class ViolationEvent:
    event_id: str
    session_id: str
    video_time_sec: float
    timestamp: str  # ISO 8601, wall-clock
    risk_score: float
    severity: str  # LOW | MEDIUM | HIGH
    primary_violation: str
    contributing_signals: List[ContributingSignal] = field(default_factory=list)
    snapshot_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
