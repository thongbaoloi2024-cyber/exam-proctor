"""FaceEmbedder — bọc facenet-pytorch (MTCNN align+crop + InceptionResnetV1
pretrained vggface2) để trích embedding 512 chiều từ 1 frame RGB.

TÁCH BIỆT với `MTCNNFaceDetector` (Perception Layer, chỉ trả bbox thô cho
FacePresenceSignal/MultiFaceSignal): InceptionResnetV1 cần khuôn mặt được
align + crop đúng chuẩn lúc huấn luyện (MTCNN của chính facenet-pytorch làm
việc này qua `mtcnn(frame)`, không phải chỉ detect bbox) — dùng bbox thô rồi
tự crop sẽ cho embedding kém chính xác hơn.

Chỉ dùng cho `IdentitySignal` (enrollment + re-verification định kỳ), không
chạy mỗi frame như MTCNNFaceDetector/FaceMeshDetector — throttle nằm trong
chính `IdentitySignal` (xem src/signals/identity.py).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np


_PROJECT_MODEL_CACHE = Path(__file__).resolve().parents[2] / "models" / "torch"


class FaceEmbedder:
    def __init__(self, device: str = "cpu") -> None:
        # Keep expensive, optional CV imports out of module import time.  This
        # lets the reporting/backend layers and IdentitySignal unit tests use
        # cosine_similarity or inject a fake embedder without installing the
        # complete PyTorch stack.
        os.environ.setdefault("TORCH_HOME", str(_PROJECT_MODEL_CACHE))
        _PROJECT_MODEL_CACHE.mkdir(parents=True, exist_ok=True)
        import torch
        from facenet_pytorch import MTCNN, InceptionResnetV1

        self._torch = torch
        self._device = device
        # select_largest=True (mặc định facenet-pytorch), keep_all=False ->
        # khi có NHIỀU khuôn mặt trong khung hình, tự động chọn khuôn mặt có
        # bbox LỚN NHẤT (gần camera nhất) — đúng yêu cầu edge case mục 4
        # (KE_HOACH_4_THANG_THEO_TUAN.md Tuần 6), đã verify qua
        # inspect.signature() trong venv trước khi dùng (không đoán).
        self._mtcnn = MTCNN(
            image_size=160,
            margin=0,
            keep_all=False,
            select_largest=True,
            post_process=True,
            device=device,
        )
        self._resnet = InceptionResnetV1(pretrained="vggface2", device=device).eval()

    def extract(self, rgb_frame: np.ndarray) -> Optional[np.ndarray]:
        """Trả về embedding 512 chiều (numpy float32) hoặc None nếu không
        tìm thấy khuôn mặt nào trong frame."""
        face_tensor = self._mtcnn(rgb_frame)
        if face_tensor is None:
            return None
        with self._torch.no_grad():
            embedding = self._resnet(face_tensor.unsqueeze(0).to(self._device))
        return embedding.squeeze(0).cpu().numpy().astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom < 1e-10:
        return 0.0
    return float(np.dot(a, b) / denom)
