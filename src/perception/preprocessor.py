"""Tiền xử lý frame thô: resize về kích thước xử lý chuẩn + chuyển màu BGR->RGB."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PreprocessedFrame:
    """Kết quả tiền xử lý 1 frame.

    `scale_x`/`scale_y` cho phép quy đổi toạ độ bbox/landmark tính trên ảnh đã
    resize (`rgb`) trở lại toạ độ ảnh gốc (`original_bgr`) khi cần vẽ overlay debug.
    """

    original_bgr: np.ndarray
    resized_bgr: np.ndarray
    rgb: np.ndarray
    scale_x: float
    scale_y: float


class FramePreprocessor:
    """Resize frame về chiều rộng xử lý cố định (giữ tỉ lệ khung hình) + convert RGB.

    Resize giúp các model nền (MTCNN/FaceMesh/YOLO) chạy ổn định tốc độ bất kể
    webcam trả về độ phân giải gì.
    """

    def __init__(self, target_width: int = 640) -> None:
        if target_width <= 0:
            raise ValueError("target_width phải > 0")
        self._target_width = target_width

    def process(self, frame_bgr: np.ndarray) -> PreprocessedFrame:
        if frame_bgr is None or frame_bgr.size == 0:
            raise ValueError("frame_bgr rỗng")

        h, w = frame_bgr.shape[:2]
        scale = self._target_width / float(w)
        target_height = max(1, round(h * scale))

        if w == self._target_width:
            resized_bgr = frame_bgr
        else:
            resized_bgr = cv2.resize(
                frame_bgr, (self._target_width, target_height), interpolation=cv2.INTER_AREA
            )

        rgb = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)

        return PreprocessedFrame(
            original_bgr=frame_bgr,
            resized_bgr=resized_bgr,
            rgb=rgb,
            scale_x=w / float(self._target_width),
            scale_y=h / float(target_height),
        )
