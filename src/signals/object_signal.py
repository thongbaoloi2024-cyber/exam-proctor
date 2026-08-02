"""ObjectSignal — phát hiện vật thể cấm (điện thoại/sách) từ YOLOv8-COCO.

Việc detect YOLO được throttle ở tầng Perception Layer (KHÔNG phải ở đây) để
tránh quá tải CPU — xem `src/perception/pipeline.py`
(`object_detect_interval_sec`). Signal này chỉ đọc `perception_result.objects`
(đã lọc sẵn đúng lớp cell phone/book), không tự gọi lại model.

Theo dõi thời gian vật thể xuất hiện LIÊN TỤC trước khi coi là "vượt ngưỡng"
— cùng triết lý với các signal khác — để tránh báo động giả từ 1 lần detect
nhầm thoáng qua.
"""

from __future__ import annotations

from src.perception.perception_result import PerceptionResult

from ._debounce import DurationDebounceTimer
from .base import SignalExtractor, SignalResult


class ObjectSignal(SignalExtractor):
    signal_name = "OBJECT_PRESENCE"

    def __init__(self, min_present_duration_sec: float = 1.0) -> None:
        self._timer = DurationDebounceTimer(min_present_duration_sec)

    def reset(self) -> None:
        self._timer.reset()

    def process(self, perception_result: PerceptionResult) -> SignalResult:
        now = perception_result.timestamp
        objects = perception_result.objects

        present_duration = self._timer.update(now, condition=bool(objects))

        if objects:
            best = max(objects, key=lambda o: o.confidence)
            metadata = {
                "object_class": best.class_name,
                "bbox": best.bbox,
                "num_objects": len(objects),
                "present_duration_sec": round(present_duration, 2),
            }
            confidence = best.confidence
        else:
            metadata = {
                "object_class": None,
                "bbox": None,
                "num_objects": 0,
                "present_duration_sec": 0.0,
            }
            confidence = 0.0

        return SignalResult(
            signal_name=self.signal_name,
            timestamp=now,
            value=float(len(objects)),
            exceeds_threshold=self._timer.exceeds(present_duration),
            confidence=confidence,
            metadata=metadata,
        )
