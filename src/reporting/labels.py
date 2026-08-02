"""Nhãn tiếng Việt ngắn gọn cho `violation_type` (enum cố định, xem
docs/DATA_SCHEMAS.md mục 1.2) — chỉ phục vụ hiển thị (biểu đồ, bảng), không
ảnh hưởng logic; nếu gặp giá trị lạ (chưa có trong bảng) thì hiển thị nguyên
văn `violation_type` thay vì lỗi."""

from __future__ import annotations

from typing import Dict

VIOLATION_TYPE_LABELS_VI: Dict[str, str] = {
    "FACE_ABSENT": "Vắng mặt",
    "MULTIPLE_FACES": "Nhiều người",
    "EYES_CLOSED": "Nhắm mắt kéo dài",
    "GAZE_AWAY": "Mắt/nhìn lệch (nhãn cũ)",
    "TALKING": "Nói chuyện",
    "OBJECT_DETECTED": "Vật thể cấm",
    "HEAD_POSE_AWAY": "Quay đầu",
    "IDENTITY_MISMATCH": "Đổi người (nghi thi hộ)",
}


def violation_type_label_vi(violation_type: str) -> str:
    return VIOLATION_TYPE_LABELS_VI.get(violation_type, violation_type)
