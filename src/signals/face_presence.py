"""FacePresenceSignal — phát hiện vắng mặt khuôn mặt liên tục.

Khác bản tham khảo (chỉ báo "no face" tức thời theo từng frame riêng lẻ):
tín hiệu này theo dõi THỜI GIAN vắng mặt liên tục (`consecutive_absent_sec`)
và chỉ coi là "vượt ngưỡng" khi khoảng vắng mặt đủ dài — tránh báo động giả
do 1-2 frame bị mất detect thoáng qua (nháy mắt, cúi đầu 1 khắc...).
"""

from __future__ import annotations

from src.perception.perception_result import PerceptionResult

from ._debounce import DurationDebounceTimer
from .base import SignalExtractor, SignalResult


class FacePresenceSignal(SignalExtractor):
    signal_name = "FACE_PRESENCE"

    def __init__(self, absence_threshold_sec: float = 2.0) -> None:
        self._timer = DurationDebounceTimer(absence_threshold_sec)

    def reset(self) -> None:
        self._timer.reset()

    def process(self, perception_result: PerceptionResult) -> SignalResult:
        now = perception_result.timestamp
        has_face = len(perception_result.face_boxes) > 0

        consecutive_absent_sec = self._timer.update(now, condition=not has_face)
        # Không có khuôn mặt -> không có gì để đo confidence detection, nhưng
        # bản thân việc "không tìm thấy" được coi là chắc chắn (1.0).
        confidence = max((box.confidence for box in perception_result.face_boxes), default=1.0)

        return SignalResult(
            signal_name=self.signal_name,
            timestamp=now,
            value=1.0 if has_face else 0.0,
            exceeds_threshold=self._timer.exceeds(consecutive_absent_sec),
            confidence=confidence,
            metadata={"consecutive_absent_sec": round(consecutive_absent_sec, 2)},
        )
