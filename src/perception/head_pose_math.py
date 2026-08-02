"""Toán học lõi cho Head Pose Estimation bằng cv2.solvePnP — dùng chung giữa
`HeadPoseSignal` (tính góc để quyết định cảnh báo) và phần vẽ trực quan debug
(trục 3D gắn lên mũi trong main.py). Xem docs/HEAD_POSE_NOTES.md cho giải
thích đầy đủ công thức/cách chọn landmark/giới hạn phương pháp — dùng cho
luận văn phần Cài đặt.

TÓM TẮT 4 BƯỚC (khớp docs/DE_CUONG_CHI_TIET.md mục 5.1.1):
1. Lấy 6 điểm landmark 2D từ MediaPipe FaceMesh.
2. Ánh xạ với mô hình khuôn mặt 3D chuẩn xấp xỉ (không đo thật).
3. Ước lượng camera matrix xấp xỉ theo độ phân giải frame (không calibrate
   camera thật).
4. Giải PnP -> rotation vector -> Rodrigues -> ma trận xoay -> góc Euler
   (yaw/pitch/roll, độ).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

from .perception_result import FaceLandmarks

# --- Bước 1: 6 điểm landmark MediaPipe FaceMesh ---
# Cằm (152): vị trí đã XÁC MINH qua thứ tự trong FACE_LANDMARKS_FACE_OVAL mà
#   package mediapipe expose (152 nằm giữa 377 và 148, đúng vị trí đáy contour
#   khuôn mặt = cằm).
# Khoé mắt ngoài (33 phải / 263 trái), khoé miệng (61 phải / 291 trái): đã
#   verify thuộc tập FACE_LANDMARKS_RIGHT_EYE/LEFT_EYE/LIPS (dùng lại đúng
#   các điểm đã verify ở EyeStateSignal/MouthStateSignal Tuần 4).
# Đỉnh mũi (1): mediapipe bản cài KHÔNG có tập FACE_LANDMARKS_NOSE để verify
#   qua topology như các điểm trên. Đối chiếu qua canonical_face_model.obj
#   (file model 3D trung tính công khai của Google, KHÔNG bundle sẵn trong
#   gói pip) cho thấy điểm 1 nằm ở vùng lồi nhất về phía camera (z lớn) và
#   x~0 (đúng trục giữa mặt) — khớp quy ước "đỉnh mũi" được dùng thống nhất
#   trong hầu hết tutorial solvePnP + MediaPipe công khai.
NOSE_TIP = 1
CHIN = 152
RIGHT_EYE_OUTER_CORNER = 33
LEFT_EYE_OUTER_CORNER = 263
RIGHT_MOUTH_CORNER = 61
LEFT_MOUTH_CORNER = 291

# Thứ tự PHẢI khớp với MODEL_POINTS_3D bên dưới (từng dòng tương ứng).
LANDMARK_INDICES: Tuple[int, int, int, int, int, int] = (
    NOSE_TIP,
    CHIN,
    LEFT_EYE_OUTER_CORNER,
    RIGHT_EYE_OUTER_CORNER,
    LEFT_MOUTH_CORNER,
    RIGHT_MOUTH_CORNER,
)

# --- Bước 2: mô hình khuôn mặt 3D chuẩn xấp xỉ (đơn vị tương đối, không đo
# thật) --- Bộ số liệu kinh điển từ Satya Mallick (LearnOpenCV, "Head Pose
# Estimation using OpenCV and Dlib"), dùng lại rộng rãi trong hầu hết
# tutorial solvePnP + landmark detector (dlib lẫn MediaPipe) vì đây là mô
# hình khuôn mặt "trung bình" mang tính minh hoạ hình học, không gắn với bộ
# landmark cụ thể nào. Ghép theo TÊN giải phẫu (trái/phải theo góc nhìn của
# CHÍNH thí sinh, không phải theo hướng nhìn của camera) để đảm bảo nhất
# quán dấu — xem docs/HEAD_POSE_NOTES.md mục "Giới hạn" về rủi ro đảo dấu
# yaw/pitch chỉ có thể xác nhận chắc chắn bằng test trực quan qua webcam
# thật.
MODEL_POINTS_3D = np.array(
    [
        (0.0, 0.0, 0.0),  # Đỉnh mũi
        (0.0, -330.0, -65.0),  # Cằm
        (-225.0, 170.0, -135.0),  # Khoé mắt ngoài TRÁI (của thí sinh)
        (225.0, 170.0, -135.0),  # Khoé mắt ngoài PHẢI (của thí sinh)
        (-150.0, -150.0, -125.0),  # Khoé miệng TRÁI
        (150.0, -150.0, -125.0),  # Khoé miệng PHẢI
    ],
    dtype=np.float64,
)


@dataclass(frozen=True)
class HeadPoseResult:
    yaw_deg: float
    pitch_deg: float
    roll_deg: float
    rotation_vector: np.ndarray
    translation_vector: np.ndarray
    camera_matrix: np.ndarray
    nose_2d_px: Tuple[float, float]


def estimate_camera_matrix(frame_shape: Tuple[int, int]) -> np.ndarray:
    """Bước 3: camera matrix xấp xỉ — KHÔNG calibrate camera thật.

    focal_length ước lượng bằng chiều rộng ảnh (quy ước phổ biến khi không có
    thông số camera thật), principal point đặt ở tâm ảnh. Sai số so với
    camera matrix calibrate thật là giới hạn đã biết, ghi rõ trong
    docs/HEAD_POSE_NOTES.md — chấp nhận được cho mục tiêu định tính (phát
    hiện xu hướng quay đầu), không dùng cho đo lường mm chính xác.
    """
    height, width = frame_shape
    focal_length = float(width)
    center = (width / 2.0, height / 2.0)
    return np.array(
        [
            [focal_length, 0.0, center[0]],
            [0.0, focal_length, center[1]],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def _rotation_matrix_to_euler_deg(rotation_matrix: np.ndarray) -> Tuple[float, float, float]:
    """Phân rã ma trận xoay 3x3 thành góc Euler (độ), quy ước R = Rz(roll) @
    Ry(yaw) @ Rx(pitch) — công thức kinh điển (Slabaugh, "Computing Euler
    angles from a rotation matrix"), đã tự kiểm chứng bằng cách dựng ma trận
    xoay từ góc biết trước rồi decode lại (xem
    tests/test_head_pose_signal.py) trước khi đưa vào đây.
    """
    sy = (rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2) ** 0.5
    singular = sy < 1e-6

    if not singular:
        pitch = np.arctan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
        yaw = np.arctan2(-rotation_matrix[2, 0], sy)
        roll = np.arctan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
    else:
        pitch = np.arctan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
        yaw = np.arctan2(-rotation_matrix[2, 0], sy)
        roll = 0.0

    return tuple(float(v) for v in np.degrees([pitch, yaw, roll]))


def solve_head_pose(landmarks: FaceLandmarks, frame_shape: Tuple[int, int]) -> Optional[HeadPoseResult]:
    """Bước 1 (đọc landmark) + Bước 4 (solvePnP + decode góc). Trả None nếu
    solvePnP không hội tụ (hiếm, thường do 6 điểm gần thẳng hàng bất thường).
    """
    image_points = np.array(
        [landmarks.to_pixel(idx, frame_shape) for idx in LANDMARK_INDICES],
        dtype=np.float64,
    )
    camera_matrix = estimate_camera_matrix(frame_shape)
    dist_coeffs = np.zeros((4, 1), dtype=np.float64)  # không calibrate thật -> giả định không méo ống kính

    success, rotation_vector, translation_vector = cv2.solvePnP(
        MODEL_POINTS_3D,
        image_points,
        camera_matrix,
        dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not success:
        return None

    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    pitch, yaw, roll = _rotation_matrix_to_euler_deg(rotation_matrix)

    return HeadPoseResult(
        yaw_deg=yaw,
        pitch_deg=pitch,
        roll_deg=roll,
        rotation_vector=rotation_vector,
        translation_vector=translation_vector,
        camera_matrix=camera_matrix,
        nose_2d_px=tuple(image_points[0]),
    )


def project_debug_axes(result: HeadPoseResult, axis_length: float = 100.0) -> Tuple[
    Tuple[float, float], Tuple[float, float], Tuple[float, float]
]:
    """Chiếu 3 điểm cuối trục X/Y/Z (gắn gốc tại mũi) xuống ảnh 2D, phục vụ
    vẽ trực quan debug (bước 4, main.py) — kiểm chứng bằng mắt góc quay có
    đúng hướng không khi test qua webcam thật.
    """
    axis_points_3d = np.array(
        [
            [axis_length, 0.0, 0.0],  # X
            [0.0, axis_length, 0.0],  # Y
            [0.0, 0.0, axis_length],  # Z
        ],
        dtype=np.float64,
    )
    dist_coeffs = np.zeros((4, 1), dtype=np.float64)
    projected, _ = cv2.projectPoints(
        axis_points_3d,
        result.rotation_vector,
        result.translation_vector,
        result.camera_matrix,
        dist_coeffs,
    )
    projected = projected.reshape(-1, 2)
    return tuple(projected[0]), tuple(projected[1]), tuple(projected[2])
