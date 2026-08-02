"""Tổng hợp thống kê từ `SessionReportData` (đã đọc thô ở `data_loader.py`)
thành `ReportSummary` — dữ liệu sẵn sàng đưa vào template báo cáo (Tuần 11):
số vi phạm theo loại/mức độ, danh sách snapshot kèm mốc thời gian, và câu
"kết luận tự động" tóm tắt đầu báo cáo.

Toàn bộ `severity` dùng ở đây được ĐỌC LẠI từ `violations[i]["severity"]`
(đã do Risk Fusion Engine, Tuần 10, tính sẵn) — module này không tính lại
severity từ risk_score, chỉ đếm/nhóm, tránh lệch với mục 3 (xem
`severity.py`)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .data_loader import SessionReportData
from .severity import SEVERITY_ORDER, severity_label_vi


@dataclass
class SnapshotEntry:
    video_time_sec: float
    snapshot_path: str
    severity: str
    primary_violation: str
    contributing_signal_names: List[str]


@dataclass
class ReportSummary:
    session_id: str
    duration_sec: float
    total_violations: int
    count_by_type: Dict[str, int] = field(default_factory=dict)
    count_by_severity: Dict[str, int] = field(default_factory=dict)
    peak_risk_score: float = 0.0
    snapshots: List[SnapshotEntry] = field(default_factory=list)
    summary_sentence: str = ""


def _infer_duration_sec(data: SessionReportData) -> float:
    if "duration_sec" in data.session_meta:
        return float(data.session_meta["duration_sec"])
    candidates = [row["video_time_sec"] for row in data.risk_timeline]
    candidates += [row["video_time_sec"] for row in data.violations]
    candidates += [row["video_time_sec"] for row in data.browser_events]
    return max(candidates) if candidates else 0.0


def _build_summary_sentence(count_by_severity: Dict[str, int], duration_sec: float) -> str:
    duration_min = duration_sec / 60.0
    total = sum(count_by_severity.values())
    if total == 0:
        return f"Không phát hiện vi phạm nào trong {duration_min:.0f} phút giám sát."

    parts = [
        f"{count_by_severity[sev]} vi phạm mức {severity_label_vi(sev).lower()}"
        for sev in reversed(SEVERITY_ORDER)  # HIGH truoc, LOW sau - dung thu tu quan trong giam dan
        if count_by_severity.get(sev, 0) > 0
    ]
    return f"Phát hiện {', '.join(parts)} trong {duration_min:.0f} phút thi."


def build_report_summary(data: SessionReportData) -> ReportSummary:
    count_by_type: Counter = Counter()
    count_by_severity: Counter = Counter({sev: 0 for sev in SEVERITY_ORDER})
    snapshots: List[SnapshotEntry] = []
    peak_risk_score = 0.0

    for violation in data.violations:
        count_by_type[violation["primary_violation"]] += 1
        count_by_severity[violation["severity"]] += 1
        peak_risk_score = max(peak_risk_score, violation["risk_score"])
        if violation.get("snapshot_path"):
            snapshots.append(
                SnapshotEntry(
                    video_time_sec=violation["video_time_sec"],
                    snapshot_path=violation["snapshot_path"],
                    severity=violation["severity"],
                    primary_violation=violation["primary_violation"],
                    contributing_signal_names=[c["signal_name"] for c in violation["contributing_signals"]],
                )
            )

    for row in data.risk_timeline:
        peak_risk_score = max(peak_risk_score, row.get("risk_score", 0.0))

    snapshots.sort(key=lambda s: s.video_time_sec)
    duration_sec = _infer_duration_sec(data)

    return ReportSummary(
        session_id=data.session_id,
        duration_sec=duration_sec,
        total_violations=len(data.violations),
        count_by_type=dict(count_by_type),
        count_by_severity=dict(count_by_severity),
        peak_risk_score=peak_risk_score,
        snapshots=snapshots,
        summary_sentence=_build_summary_sentence(dict(count_by_severity), duration_sec),
    )
