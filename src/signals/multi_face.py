"""MultiFaceSignal — đếm số khuôn mặt độ tin cậy cao trong khung hình.

Lọc lại theo `confidence_threshold` riêng của signal (độc lập với ngưỡng lọc
đã áp dụng ở `MTCNNFaceDetector`) để có thể tinh chỉnh độ nhạy multi-face mà
không ảnh hưởng tới các signal khác cũng dùng chung `face_boxes`
(VD FacePresenceSignal muốn ngưỡng thấp hơn để không bỏ sót, MultiFaceSignal
muốn ngưỡng cao hơn để tránh đếm nhầm phản chiếu/ảnh trên tường).
"""

from __future__ import annotations

from src.perception.perception_result import PerceptionResult

from .base import SignalExtractor, SignalResult


class MultiFaceSignal(SignalExtractor):
    signal_name = "MULTI_FACE"

    def __init__(self, confidence_threshold: float = 0.90) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold phải trong [0, 1]")
        self._confidence_threshold = confidence_threshold

    def process(self, perception_result: PerceptionResult) -> SignalResult:
        high_conf_boxes = [
            box for box in perception_result.face_boxes if box.confidence >= self._confidence_threshold
        ]
        count = len(high_conf_boxes)
        confidence = max((box.confidence for box in high_conf_boxes), default=0.0)

        return SignalResult(
            signal_name=self.signal_name,
            timestamp=perception_result.timestamp,
            value=float(count),
            exceeds_threshold=count > 1,
            confidence=confidence,
            metadata={"face_boxes": [box.bbox for box in high_conf_boxes]},
        )
