"""Bọc MTCNN (facenet-pytorch) thành 1 component của Perception Layer.

Chỉ dùng cho phát hiện khuôn mặt (bbox + confidence) — MTCNN cũng cung cấp
landmark 5 điểm nhưng chưa cần ở Tuần 3 (head pose Tuần 5 dùng landmark 468
điểm từ MediaPipe FaceMesh, không phải landmark của MTCNN).
"""

from __future__ import annotations

from typing import List

import numpy as np
from facenet_pytorch import MTCNN

from .perception_result import FaceBox


class MTCNNFaceDetector:
    """Phát hiện mọi khuôn mặt trong 1 frame RGB bằng MTCNN.

    `min_confidence` chỉ loại phát hiện rất yếu. MultiFaceSignal áp dụng
    ngưỡng cao hơn riêng của nó, nhờ đó FacePresenceSignal có thể ưu tiên
    recall trong khi MULTI_FACE vẫn ưu tiên precision.
    """

    def __init__(self, device: str = "cpu", min_confidence: float = 0.60) -> None:
        self._min_confidence = min_confidence
        # keep_all=True: trả về TẤT CẢ khuôn mặt tìm được (không chỉ 1 cái tốt nhất)
        # — bắt buộc để MultiFaceSignal đếm được nhiều khuôn mặt.
        self._mtcnn = MTCNN(keep_all=True, device=device)

    def detect(self, rgb_frame: np.ndarray) -> List[FaceBox]:
        boxes, probs = self._mtcnn.detect(rgb_frame)
        if boxes is None:
            return []

        face_boxes: List[FaceBox] = []
        for box, prob in zip(boxes, probs):
            if prob is None or prob < self._min_confidence:
                continue
            x1, y1, x2, y2 = (float(v) for v in box)
            face_boxes.append(FaceBox(bbox=(x1, y1, x2, y2), confidence=float(prob)))
        return face_boxes
