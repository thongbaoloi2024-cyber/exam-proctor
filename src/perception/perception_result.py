"""Cấu trúc dữ liệu output của Perception Layer, đọc bởi mọi Signal Extractor.

Theo docs/DATA_SCHEMAS.md: Perception Layer chạy các model nền tảng (MTCNN,
FaceMesh, YOLO) một lần mỗi frame, kết quả gói trong `PerceptionResult` để các
signal extractor dùng chung — tránh chạy trùng detector nhiều lần/frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class FaceBox:
    """1 khuôn mặt phát hiện được bởi MTCNN, toạ độ theo ảnh đã resize (rgb)."""

    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)


@dataclass(frozen=True)
class FaceLandmarks:
    """468 điểm landmark của khuôn mặt CHÍNH (MediaPipe FaceLandmarker,
    num_faces=1 — chỉ theo dõi thí sinh chính, khác MTCNN đa khuôn mặt).

    Toạ độ CHUẨN HOÁ [0, 1] theo ảnh đã resize (`rgb`), không phải pixel —
    dùng `frame_shape` của `PerceptionResult` để quy đổi ra pixel khi cần.
    """

    points: Tuple[Tuple[float, float], ...]  # index 0..467, mỗi phần tử (x, y)

    def get(self, index: int) -> Tuple[float, float]:
        return self.points[index]

    def to_pixel(self, index: int, frame_shape: Tuple[int, int]) -> Tuple[float, float]:
        height, width = frame_shape
        x, y = self.points[index]
        return x * width, y * height


@dataclass(frozen=True)
class ObjectBox:
    """1 vật thể (điện thoại/sách) phát hiện được bởi YOLOv8, toạ độ theo
    ảnh đã resize (`resized_bgr`)."""

    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float
    class_name: str


@dataclass
class PerceptionResult:
    """Output tổng hợp của Perception Layer cho 1 frame."""

    timestamp: float
    frame_shape: Tuple[int, int]  # (height, width) của ảnh đã resize
    face_boxes: List[FaceBox] = field(default_factory=list)
    face_landmarks: Optional[FaceLandmarks] = None
    objects: List[ObjectBox] = field(default_factory=list)
    # Ảnh RGB gốc (đã resize) của frame này — Tuần 6 bổ sung, dành riêng cho
    # IdentitySignal (cần pixel thật để tự chạy MTCNN+InceptionResnetV1 trích
    # embedding, không dùng chung được với face_boxes/landmarks vốn chỉ là
    # toạ độ). Optional để các signal khác (không cần pixel) không bị ảnh
    # hưởng — chỉ là 1 reference tới mảng đã có sẵn (preprocessed.rgb), không
    # copy thêm bộ nhớ.
    rgb_frame: Optional[np.ndarray] = None
