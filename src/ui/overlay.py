"""Cac ham ve thuan (khong giu state), tach ra tu main() cu (Tuan 3-11) +
`_draw_head_pose_axes` - CHI DI CHUYEN, khong viet lai logic ve da chay dung
qua webcam that o Tuan 8 (mau theo STATE_COLOR, dong "IDENTITY: ... warning=...").
"""
from __future__ import annotations

from typing import Dict, List, Optional

import cv2
import numpy as np

from src.fusion.signal_state_machine import SignalState
from src.perception.head_pose_math import HeadPoseResult, project_debug_axes
from src.perception.perception_result import PerceptionResult
from src.signals.base import SignalResult

from .button import Button
from .text_field import TextField

STATE_COLOR = {
    SignalState.NORMAL: (0, 255, 255),      # vang
    SignalState.SUSPICIOUS: (0, 165, 255),  # cam
    SignalState.ALERT: (0, 0, 255),         # do
}


def draw_idle_screen(
    frame: np.ndarray,
    name_field: TextField,
    code_field: TextField,
    start_button: Button,
    error_message: Optional[str] = None,
) -> None:
    cv2.putText(
        frame, "He thong Giam sat Thi bang CV", (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA,
    )
    name_field.draw(frame)
    code_field.draw(frame)
    start_button.draw(frame)
    if error_message:
        cv2.putText(
            frame, error_message, (20, start_button.rect[1] + start_button.rect[3] + 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 1, cv2.LINE_AA,
        )


def draw_enrollment_progress(
    frame: np.ndarray, count: int, total: int, liveness_prompt: Optional[str] = None,
) -> None:
    cv2.putText(
        frame, f"Dang dang ky khuon mat... {count}/{total}", (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA,
    )
    if liveness_prompt:
        cv2.putText(
            frame, f"Kiem tra song: {liveness_prompt}", (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA,
        )


def _draw_head_pose_axes(display: np.ndarray, head_pose_result: SignalResult) -> None:
    """Ve truc 3D (X do/Y xanh la/Z xanh duong) gan len mui - kiem chung
    truc quan goc quay dau co dung huong khong (Tuan 5)."""
    metadata = head_pose_result.metadata
    if metadata.get("rotation_vector") is None:
        return

    result = HeadPoseResult(
        yaw_deg=metadata["yaw"],
        pitch_deg=metadata["pitch"],
        roll_deg=metadata["roll"],
        rotation_vector=np.array(metadata["rotation_vector"]),
        translation_vector=np.array(metadata["translation_vector"]),
        camera_matrix=np.array(metadata["camera_matrix"]),
        nose_2d_px=tuple(metadata["nose_2d_px"]),
    )
    x_end, y_end, z_end = project_debug_axes(result, axis_length=100.0)
    nose = tuple(int(v) for v in result.nose_2d_px)
    cv2.line(display, nose, tuple(int(v) for v in x_end), (0, 0, 255), 2)  # X - do
    cv2.line(display, nose, tuple(int(v) for v in y_end), (0, 255, 0), 2)  # Y - xanh la
    cv2.line(display, nose, tuple(int(v) for v in z_end), (255, 0, 0), 2)  # Z - xanh duong
    cv2.putText(
        display,
        f"yaw={metadata['yaw']:.1f} pitch={metadata['pitch']:.1f} roll={metadata['roll']:.1f}",
        (nose[0] + 10, nose[1]),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA,
    )


def draw_monitoring_overlay(
    display: np.ndarray,
    perception_result: PerceptionResult,
    results: List[SignalResult],
    states: Dict[str, SignalState],
    session_state_value: str,
    end_button: Button,
) -> None:
    for box in perception_result.face_boxes:
        x1, y1, x2, y2 = (int(v) for v in box.bbox)
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
    for obj in perception_result.objects:
        x1, y1, x2, y2 = (int(v) for v in obj.bbox)
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(
            display, obj.class_name, (x1, max(0, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA,
        )

    for i, result in enumerate(results):
        state = states.get(result.signal_name)
        color = STATE_COLOR.get(state, (255, 255, 255))
        extra = ""
        if result.signal_name == "IDENTITY":
            extra = f" warning={result.metadata.get('warning')}"
        state_label = state.value if state is not None else "?"
        line = f"{result.signal_name}: value={result.value:.2f} state={state_label}{extra}"
        cv2.putText(
            display, line, (10, 25 + 20 * i),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
        )
        if result.signal_name == "HEAD_POSE":
            _draw_head_pose_axes(display, result)

    session_color = (0, 0, 255) if session_state_value == "SESSION_ALERT" else (0, 255, 0)
    cv2.putText(
        display, f"SESSION: {session_state_value}",
        (10, display.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, session_color, 2, cv2.LINE_AA,
    )
    end_button.draw(display)


def draw_generating_report_message(frame: np.ndarray) -> None:
    cv2.putText(
        frame, "Dang tao bao cao...", (20, frame.shape[0] // 2),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA,
    )


def draw_ended_screen(frame: np.ndarray, summary_sentence: str, report_path: Optional[str]) -> None:
    cv2.putText(
        frame, "Phien giam sat da ket thuc.", (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA,
    )
    cv2.putText(
        frame, summary_sentence, (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA,
    )
    if report_path:
        cv2.putText(
            frame, f"Bao cao: {report_path}", (20, 110),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA,
        )
