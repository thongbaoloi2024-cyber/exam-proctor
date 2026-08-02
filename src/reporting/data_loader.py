"""Đọc dữ liệu thô của 1 phiên giám sát từ thư mục `sessions/<session_id>/`
(đúng cấu trúc docs/DATA_SCHEMAS.md mục 4) — bước đầu tiên của module báo
cáo (Tuần 11). Chỉ đọc & parse, KHÔNG tính toán thống kê (xem
`aggregator.py`) — tách 2 việc để dễ test riêng từng phần.

Dung nạp (tolerant) với file thiếu: 1 phiên chạy dở/crash giữa chừng vẫn cần
sinh được báo cáo từ dữ liệu có sẵn, không nên bắt buộc đủ mọi file mới chạy
được — đúng tinh thần "báo cáo xem lại sau khi thi" cần hoạt động cả với dữ
liệu không hoàn chỉnh.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Union


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class SessionReportData:
    session_id: str
    session_dir: Path
    session_meta: Dict[str, Any] = field(default_factory=dict)
    violations: List[Dict[str, Any]] = field(default_factory=list)
    risk_timeline: List[Dict[str, Any]] = field(default_factory=list)
    state_transitions: List[Dict[str, Any]] = field(default_factory=list)
    browser_events: List[Dict[str, Any]] = field(default_factory=list)


def load_session_report_data(session_dir: Union[str, Path]) -> SessionReportData:
    session_dir = Path(session_dir)
    session_id = session_dir.name

    return SessionReportData(
        session_id=session_id,
        session_dir=session_dir,
        session_meta=_read_json(session_dir / "session_meta.json"),
        violations=_read_jsonl(session_dir / "violations.jsonl"),
        risk_timeline=_read_jsonl(session_dir / "risk_score_timeline.jsonl"),
        state_transitions=_read_jsonl(session_dir / "state_transitions.jsonl"),
        browser_events=_read_jsonl(session_dir / "browser_events.jsonl"),
    )
