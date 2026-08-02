"""Button - hit-test hinh chu nhat thuan, khong phu thuoc cv2 event that
(cho phep test khong can mo cua so that)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np


@dataclass
class Button:
    rect: Tuple[int, int, int, int]  # x, y, w, h
    label: str

    def contains(self, px: int, py: int) -> bool:
        """Quy uoc: bien trai/tren tinh la "trong", bien phai/duoi tinh la
        "ngoai" (nua khoang [x, x+w) x [y, y+h)) - tranh mo ho o dung bien."""
        x, y, w, h = self.rect
        return x <= px < x + w and y <= py < y + h

    def draw(self, frame: np.ndarray) -> None:
        x, y, w, h = self.rect
        cv2.rectangle(frame, (x, y), (x + w, y + h), (80, 80, 80), -1)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 2)
        text_size = cv2.getTextSize(self.label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        text_x = x + max(0, (w - text_size[0]) // 2)
        text_y = y + (h + text_size[1]) // 2
        cv2.putText(
            frame, self.label, (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA,
        )
