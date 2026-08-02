"""TextField - o nhap van ban don gian cho cua so OpenCV (man hinh IDLE
nhap ten + join-code truoc khi vao ENROLLMENT). OpenCV khong co widget nhap
lieu san - tu cai dat bang cach bat phim qua cv2.waitKey va tich luy ky tu,
cung tinh than voi quyet dinh "khong them PyQt/Tkinter" da chot ở
docs/KE_HOACH_CHI_TIET_TUAN12.md muc 1."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np

_BACKSPACE_KEYS = (8, 127)
_MAX_LENGTH = 40


@dataclass
class TextField:
    rect: Tuple[int, int, int, int]  # x, y, w, h
    label: str
    value: str = ""
    active: bool = False
    uppercase: bool = False

    def contains(self, px: int, py: int) -> bool:
        x, y, w, h = self.rect
        return x <= px < x + w and y <= py < y + h

    def handle_key(self, key: int) -> None:
        if not self.active:
            return
        if key in _BACKSPACE_KEYS:
            self.value = self.value[:-1]
            return
        if 32 <= key <= 126 and len(self.value) < _MAX_LENGTH:
            char = chr(key)
            self.value += char.upper() if self.uppercase else char

    def draw(self, frame: np.ndarray) -> None:
        x, y, w, h = self.rect
        border_color = (0, 255, 255) if self.active else (150, 150, 150)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (40, 40, 40), -1)
        cv2.rectangle(frame, (x, y), (x + w, y + h), border_color, 2)
        cv2.putText(
            frame, f"{self.label}: {self.value}", (x + 8, y + h // 2 + 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA,
        )
