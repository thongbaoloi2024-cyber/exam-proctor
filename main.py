"""Entry point mong - tao AppConfig/signals tu config/fusion.yaml, dung
AppController cho toan bo logic (Tuan 13, xem docs/KE_HOACH_CHI_TIET_TUAN12.md
va docs/KE_HOACH_PLATFORM.md). Thay the hoan toan ban main.py cu (2 vong lap
`while` tach biet, tham so signal hardcode - xem lich su Tuan 3-11 qua git
log neu can doi chieu).

Man hinh IDLE yeu cau nhap ten + ma tham gia (join-code) CHI KHI
`config/fusion.yaml` muc `backend.enabled: true` (mac dinh false - giu
nguyen luong 1-may cu, khong can docker compose dang chay). Bat len khi
muon giam thi theo doi qua dashboard (xem docs/KE_HOACH_PLATFORM.md).

Chay: python main.py   (can venv da activate, can webcam that)
Bam nut "Bat dau" -> nhin thang camera de dang ky khuon mat -> giam sat ->
bam nut "Ket thuc" hoac phim 'q'/ESC de ket thuc phien.
"""
from __future__ import annotations

import sys

import cv2

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from src.app_config import AppConfig
from src.app_controller import AppController
from src.perception.frame_source import FrameSource
from src.perception.pipeline import PerceptionLayer
from src.signals.factory import build_signals_from_config
from src.ui.app_state import AppState

FUSION_CONFIG_PATH = "config/fusion.yaml"


def _mouse_callback(event: int, x: int, y: int, flags: int, controller: AppController) -> None:
    controller.handle_mouse(event, x, y)


def _read_frame_for_state(
    source: FrameSource,
    state: AppState,
    is_file_source: bool,
    paused_frame,
):
    """Read the next frame, keeping a file source still while the user logs in.

    A webcam must keep refreshing on the IDLE screen, but a demo clip should
    not be consumed while the candidate is typing their name and join code.
    ``paused_frame`` is intentionally passed in and returned so this behavior
    is easy to exercise without opening an OpenCV window.
    """
    if is_file_source and state == AppState.IDLE:
        if paused_frame is None:
            paused_frame = source.read()
        return paused_frame, paused_frame

    return source.read(), None


def main() -> None:
    config = AppConfig.from_yaml(FUSION_CONFIG_PATH)
    signals = build_signals_from_config(FUSION_CONFIG_PATH)
    perception = PerceptionLayer()  # object_detect_interval_sec mac dinh 0.4s
    controller = AppController(config, signals, perception, fusion_config_path=FUSION_CONFIG_PATH)

    cv2.namedWindow(config.camera.window_name)
    cv2.setMouseCallback(config.camera.window_name, _mouse_callback, controller)

    print(f"Mo webcam (source={config.camera.source})... bam 'Bat dau' de vao phien giam sat.")
    try:
        with FrameSource(source=config.camera.source) as source:
            is_file_source = isinstance(config.camera.source, str)
            paused_frame = None
            while True:
                raw_frame, paused_frame = _read_frame_for_state(
                    source, controller.state, is_file_source, paused_frame,
                )
                if raw_frame is None:
                    print("Khong doc duoc frame tu webcam - dung lai.")
                    break

                display = controller.step(raw_frame)
                cv2.imshow(config.camera.window_name, display)

                key = cv2.waitKeyEx(1)
                controller.handle_key(key)

                if controller.state == AppState.ENDED:
                    cv2.imshow(config.camera.window_name, display)
                    cv2.waitKey(2000)  # giu man hinh ket qua vai giay truoc khi thoat
                    break
    finally:
        controller.shutdown()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
