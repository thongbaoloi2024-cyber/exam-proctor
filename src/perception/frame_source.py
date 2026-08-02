"""Đọc frame từ webcam (hoặc file video, dùng chung interface để test)."""

from __future__ import annotations

import time
from typing import Optional

import cv2
import numpy as np


class FrameSource:
    """Bọc `cv2.VideoCapture`, cung cấp interface đọc frame ổn định.

    Dùng chung cho cả webcam (device_index kiểu int) và file video (path kiểu str)
    để có thể tái sử dụng cùng lớp này khi chạy pipeline trên clip test (Tuần 13).
    """

    def __init__(
        self,
        source: int | str = 0,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> None:
        self._source = source
        self._width = width
        self._height = height
        self._cap: Optional[cv2.VideoCapture] = None

    def open(self) -> None:
        if self._cap is not None:
            return
        cap = cv2.VideoCapture(self._source)
        if self._width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        if self._height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"Không mở được nguồn frame: {self._source!r}")
        self._cap = cap

    def read(self) -> Optional[np.ndarray]:
        """Trả về 1 frame BGR (np.ndarray) hoặc None nếu hết/đọc lỗi."""
        if self._cap is None:
            raise RuntimeError("FrameSource chưa được open(). Gọi open() trước hoặc dùng context manager.")
        ok, frame = self._cap.read()
        if not ok:
            return None
        return frame

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def __enter__(self) -> "FrameSource":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


def now() -> float:
    """Timestamp dùng thống nhất trong toàn pipeline (unix epoch, giây, float)."""
    return time.time()
