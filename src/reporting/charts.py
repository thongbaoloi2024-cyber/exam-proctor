"""Sinh 2 biểu đồ cho báo cáo (Tuần 11) bằng matplotlib, trả về PNG dạng
base64 (nhúng thẳng vào HTML qua `data:image/png;base64,...` — không cần
quản lý file ảnh rời, PDF xuất ra tự chứa toàn bộ nội dung trong 1 file).

Màu sắc: severity dùng ĐÚNG bảng `severity.py` (nguồn duy nhất, xem module
đó) — không định nghĩa màu severity riêng ở đây. Đường risk_score (1 chuỗi
duy nhất) và cột đếm vi phạm dùng 1 màu xanh trung tính cố định (không phải
màu severity) để không gây nhầm "màu xanh này nghĩa là mức thấp" — độ
nghiêm trọng CHỈ được biểu diễn bằng màu severity ở đúng những nơi thể hiện
severity (vùng tô nền theo ngưỡng, chấm đánh dấu vi phạm), tránh 2 hệ màu
chồng chéo gây hiểu nhầm."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Dict, List, Optional

import matplotlib

matplotlib.use("Agg")  # backend khong can man hinh - chi xuat file/bytes

import matplotlib.pyplot as plt

from .labels import violation_type_label_vi
from .severity import SEVERITY_COLORS, SEVERITY_ORDER, severity_color, severity_label_vi

_LINE_BLUE = "#1c5cab"  # sequential blue step 550 - mau trung tinh cho du lieu khong phai severity
_BAR_BLUE = "#256abf"   # sequential blue step 500


def _fig_to_base64_png(fig) -> str:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def render_risk_timeline_chart(
    risk_timeline: List[dict],
    violations: List[dict],
    t_enter: float,
    t_exit: float,
    severity_medium_min: float,
    severity_high_min: float,
) -> Optional[str]:
    """Biểu đồ risk_score theo thời gian (phút), tô nền theo vùng severity
    (LOW/MEDIUM/HIGH), và đánh dấu các thời điểm sinh ViolationEvent bằng
    chấm màu severity.

    `severity_medium_min`/`severity_high_min` PHẢI là giá trị đã áp mặc định
    (qua `src/fusion/config.resolve_severity_thresholds`) — KHÔNG suy ra
    bằng `t_enter` ở đây, vì `severity_medium_min` có thể được cấu hình khác
    `t_enter` trong YAML (2 khái niệm độc lập: `t_enter` là ngưỡng hysteresis
    vào ALERT ở tầng phiên, `severity_medium_min` là ngưỡng phân loại
    LOW/MEDIUM - trùng giá trị mặc định nhưng không bắt buộc luôn bằng
    nhau). `t_enter`/`t_exit` ở đây chỉ dùng để vẽ 2 đường tham chiếu
    hysteresis phiên, tách biệt với vùng tô severity."""
    if not risk_timeline:
        return None

    minutes = [row["video_time_sec"] / 60.0 for row in risk_timeline]
    scores = [row["risk_score"] for row in risk_timeline]
    y_max = max(max(scores), severity_high_min * 1.15, 1.0)

    fig, ax = plt.subplots(figsize=(9, 3.4))

    # Vung nen theo severity - LOW (duoi severity_medium_min) khong to mau
    # (mac dinh la "binh thuong"), MEDIUM [severity_medium_min,
    # severity_high_min), HIGH [severity_high_min, +).
    ax.axhspan(0, severity_medium_min, color=SEVERITY_COLORS["LOW"], alpha=0.06, zorder=0)
    ax.axhspan(severity_medium_min, severity_high_min, color=SEVERITY_COLORS["MEDIUM"], alpha=0.10, zorder=0)
    ax.axhspan(severity_high_min, y_max, color=SEVERITY_COLORS["HIGH"], alpha=0.10, zorder=0)

    ax.plot(minutes, scores, color=_LINE_BLUE, linewidth=2, zorder=3, solid_capstyle="round")

    ax.axhline(t_enter, color="#4b5563", linestyle="--", linewidth=1, alpha=0.7, zorder=2)
    ax.text(
        minutes[-1], t_enter, "  T_enter", color="#4b5563", fontsize=8,
        va="center", ha="left", alpha=0.9,
    )
    ax.axhline(t_exit, color="#9ca3af", linestyle="--", linewidth=1, alpha=0.6, zorder=2)
    ax.text(minutes[-1], t_exit, "  T_exit", color="#9ca3af", fontsize=8, va="center", ha="left", alpha=0.9)

    for violation in violations:
        ax.scatter(
            violation["video_time_sec"] / 60.0, violation["risk_score"],
            color=severity_color(violation["severity"]), s=55, zorder=4,
            edgecolors="white", linewidths=0.8,
        )

    ax.set_xlabel("Thời gian (phút)")
    ax.set_ylabel("Risk score")
    ax.set_xlim(0, max(minutes[-1], 0.1))
    ax.set_ylim(0, y_max)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.8, zorder=0)

    legend_handles = [
        plt.Line2D(
            [0], [0], marker="o", color="none", markerfacecolor=severity_color(sev),
            markeredgecolor="white", markersize=8, label=severity_label_vi(sev),
        )
        for sev in SEVERITY_ORDER
    ]
    ax.legend(
        handles=legend_handles, title="Vi phạm theo mức độ", loc="upper left",
        bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=8, title_fontsize=8,
    )

    fig.tight_layout()
    return _fig_to_base64_png(fig)


def render_violation_type_chart(count_by_type: Dict[str, int]) -> Optional[str]:
    """Biểu đồ cột ngang số vi phạm theo loại (`primary_violation`), sắp xếp
    giảm dần — 1 màu duy nhất (không phải màu series) vì đây là 1 đại lượng
    (số lượng) theo danh mục đã có nhãn chữ trên trục, không cần mã màu định
    danh lặp lại."""
    if not count_by_type:
        return None

    items = sorted(count_by_type.items(), key=lambda kv: kv[1])
    labels = [violation_type_label_vi(name) for name, _ in items]
    counts = [count for _, count in items]

    fig, ax = plt.subplots(figsize=(7, 0.5 * len(items) + 1.2))
    bars = ax.barh(labels, counts, color=_BAR_BLUE, height=0.6)
    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_width() + max(counts) * 0.02, bar.get_y() + bar.get_height() / 2,
            str(count), va="center", ha="left", fontsize=9, color="#1f2937",
        )

    ax.set_xlabel("Số lần vi phạm")
    ax.set_xlim(0, max(counts) * 1.15)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    fig.tight_layout()
    return _fig_to_base64_png(fig)
