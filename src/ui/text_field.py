"""TextField - o nhap van ban don gian cho cua so OpenCV (man hinh IDLE
nhap ten + join-code truoc khi vao ENROLLMENT). OpenCV khong co widget nhap
lieu san - tu cai dat bang cach bat phim qua cv2.waitKey va tich luy ky tu,
cung tinh than voi quyet dinh "khong them PyQt/Tkinter" da chot ở
docs/KE_HOACH_CHI_TIET_TUAN12.md muc 1."""
from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass, field
from typing import Tuple

import cv2
import numpy as np

from .typography import FONT_FACE, TEXT_SCALE_BODY, TEXT_THICKNESS_REGULAR

_BACKSPACE_KEYS = (8, 127)
_CTRL_A = 1
_CTRL_C = 3
_CTRL_V = 22
_CTRL_X = 24
_MAX_LENGTH = 40


def get_clipboard_text() -> str:
    """Read Unicode text from the native clipboard.

    The desktop demo currently runs on Windows, where using the Win32
    clipboard API avoids adding another package just for paste support. On
    other platforms this safely becomes a no-op rather than breaking text
    entry or test collection.
    """
    if sys.platform != "win32":
        return ""

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_bool
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_bool
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_bool

    # CF_UNICODETEXT
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(13)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def set_clipboard_text(value: str) -> bool:
    """Write Unicode text to the native clipboard; return success status."""
    if sys.platform != "win32":
        return False

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_bool
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.c_bool
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_bool
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_bool
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p

    if not user32.OpenClipboard(None):
        return False

    handle = None
    try:
        if not user32.EmptyClipboard():
            return False
        buffer = ctypes.create_unicode_buffer(value)
        byte_count = ctypes.sizeof(buffer)
        handle = kernel32.GlobalAlloc(0x0002, byte_count)  # GMEM_MOVEABLE
        if not handle:
            return False
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return False
        try:
            ctypes.memmove(pointer, buffer, byte_count)
        finally:
            kernel32.GlobalUnlock(handle)

        # Ownership transfers to the clipboard on success.
        if user32.SetClipboardData(13, handle):  # CF_UNICODETEXT
            handle = None
            return True
        return False
    finally:
        if handle:
            kernel32.GlobalFree(handle)
        user32.CloseClipboard()


@dataclass
class TextField:
    rect: Tuple[int, int, int, int]  # x, y, w, h
    label: str
    value: str = ""
    active: bool = False
    uppercase: bool = False
    _selected_all: bool = field(default=False, init=False, repr=False)

    def contains(self, px: int, py: int) -> bool:
        x, y, w, h = self.rect
        return x <= px < x + w and y <= py < y + h

    def handle_key(self, key: int) -> None:
        if not self.active:
            return

        # waitKeyEx can return platform-specific high bits. Clipboard control
        # keys are still represented by their low-byte ASCII control value.
        key &= 0xFF
        if key == _CTRL_A:
            self._selected_all = True
            return
        if key == _CTRL_C:
            set_clipboard_text(self.value)
            return
        if key == _CTRL_X:
            set_clipboard_text(self.value)
            self.value = ""
            self._selected_all = False
            return
        if key == _CTRL_V:
            pasted = get_clipboard_text()
            if pasted:
                self._insert_text(pasted)
            return
        if key in _BACKSPACE_KEYS:
            if self._selected_all:
                self.value = ""
                self._selected_all = False
            else:
                self.value = self.value[:-1]
            return
        if 32 <= key <= 126 and len(self.value) < _MAX_LENGTH:
            self._insert_text(chr(key))

    def _insert_text(self, text: str) -> None:
        """Insert sanitized clipboard/keyboard text, replacing Ctrl+A selection."""
        text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
        text = "".join(char for char in text if char.isprintable())
        if self.uppercase:
            text = text.upper()
        if self._selected_all:
            self.value = ""
            self._selected_all = False
        available = _MAX_LENGTH - len(self.value)
        if available > 0:
            self.value += text[:available]

    def draw(self, frame: np.ndarray) -> None:
        x, y, w, h = self.rect
        border_color = (0, 255, 255) if self.active else (150, 150, 150)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (40, 40, 40), -1)
        cv2.rectangle(frame, (x, y), (x + w, y + h), border_color, 2)
        cv2.putText(
            frame, f"{self.label}: {self.value}", (x + 8, y + h // 2 + 6),
            FONT_FACE, TEXT_SCALE_BODY, (255, 255, 255),
            TEXT_THICKNESS_REGULAR, cv2.LINE_AA,
        )
