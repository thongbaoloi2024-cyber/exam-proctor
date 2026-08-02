"""Bọc MediaPipe FaceLandmarker (Tasks API) — nguồn landmark 468 điểm cho
EyeStateSignal, MouthStateSignal (Tuần 4), và HeadPoseSignal (Tuần 5).

Lưu ý kỹ thuật quan trọng: bản mediapipe cài trong venv (0.10.35, wheel
Windows) KHÔNG còn API cũ `mediapipe.solutions.face_mesh.FaceMesh` — chỉ còn
Tasks API mới (`mediapipe.tasks.python.vision.FaceLandmarker`), đã xác minh
trực tiếp bằng cách import thử trong venv trước khi viết code này (không suy
đoán). Dùng Tasks API cần 1 file model `.task` tải riêng (không tự bundle
sẵn trong package như MTCNN/YOLO), theo hướng dẫn chính thức của Google:
https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python

Chỉ theo dõi khuôn mặt CHÍNH (`num_faces=1`) — khác `MTCNNFaceDetector` (đa
khuôn mặt, dùng cho FacePresenceSignal/MultiFaceSignal). FaceMesh ở đây chỉ
phục vụ các tín hiệu landmark-based của MỘT thí sinh chính.
"""

from __future__ import annotations

import os
import urllib.request
from typing import Optional, Tuple

import mediapipe as mp
import numpy as np

from .perception_result import FaceLandmarks

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_MODEL_PATH = os.path.join(_PROJECT_ROOT, "models", "face_landmarker.task")


def _ensure_model_downloaded(model_path: str, model_url: str) -> None:
    if os.path.exists(model_path):
        return
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    try:
        urllib.request.urlretrieve(model_url, model_path)
    except Exception as exc:  # pragma: no cover - phụ thuộc mạng, khó test tự động
        raise RuntimeError(
            f"Không tải được model FaceLandmarker từ {model_url!r}. "
            f"Kiểm tra kết nối mạng, hoặc tải thủ công và đặt vào {model_path!r}."
        ) from exc


class FaceMeshDetector:
    def __init__(
        self,
        model_path: str = _DEFAULT_MODEL_PATH,
        model_url: str = _MODEL_URL,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        _ensure_model_downloaded(model_path, model_url)

        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)

    def detect(self, rgb_frame: np.ndarray) -> Optional[FaceLandmarks]:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._landmarker.detect(mp_image)
        if not result.face_landmarks:
            return None

        primary_face = result.face_landmarks[0]
        points: Tuple[Tuple[float, float], ...] = tuple((lm.x, lm.y) for lm in primary_face)
        return FaceLandmarks(points=points)
