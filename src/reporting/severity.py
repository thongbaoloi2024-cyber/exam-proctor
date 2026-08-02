"""Nguồn DUY NHẤT ánh xạ severity -> màu hiển thị, dùng chung cho MỌI nơi
trong module báo cáo (biểu đồ matplotlib, badge HTML/PDF) — tránh đúng lỗi
đã ghi nhận ở dự án tham khảo: severity map định nghĩa lệch nhau giữa các
module (VD 1 chỗ tô đỏ cho "high", chỗ khác lại tô đỏ cho "critical").

QUAN TRỌNG: severity CHÍNH nó (chuỗi "LOW"/"MEDIUM"/"HIGH") không được tính
lại ở đây — nó đã được `RiskFusionEngine._severity()` (Tuần 10,
`src/fusion/engine.py`) tính 1 LẦN DUY NHẤT dựa trên `severity_medium_min`/
`severity_high_min` đọc từ `config/fusion.yaml`, rồi ghi thẳng vào
`ViolationEvent.severity`. Module báo cáo chỉ ĐỌC LẠI giá trị đã có sẵn đó,
không suy luận lại từ risk_score — đảm bảo báo cáo luôn khớp 100% với quyết
định thật của Risk Fusion Engine lúc chạy, dù công thức severity có đổi sau
này (Tuần 14 tinh chỉnh) cũng không cần sửa module báo cáo.

Bảng màu lấy từ status palette đã kiểm chứng (colorblind-safe, tương phản đủ
khi đi kèm nhãn chữ - không dùng màu đơn độc để truyền đạt ý nghĩa)."""

from __future__ import annotations

from typing import Dict, List

SEVERITY_ORDER: List[str] = ["LOW", "MEDIUM", "HIGH"]

SEVERITY_COLORS: Dict[str, str] = {
    "LOW": "#0ca30c",     # good
    "MEDIUM": "#fab219",  # warning
    "HIGH": "#d03b3b",    # critical
}

SEVERITY_LABELS_VI: Dict[str, str] = {
    "LOW": "Thấp",
    "MEDIUM": "Trung bình",
    "HIGH": "Cao",
}

_DEFAULT_COLOR = "#6b7280"  # xam trung tinh - fallback neu gap severity la (khong nen xay ra)


def severity_color(severity: str) -> str:
    return SEVERITY_COLORS.get(severity, _DEFAULT_COLOR)


def severity_label_vi(severity: str) -> str:
    return SEVERITY_LABELS_VI.get(severity, severity)
