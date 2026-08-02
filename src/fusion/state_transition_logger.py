"""StateTransitionLogger — ghi mỗi lần đổi trạng thái (per-signal HOẶC sau
này session, Tuần 10) ra file JSONL, đúng định dạng `state_transitions.jsonl`
ở docs/DATA_SCHEMAS.md mục 4. CHỈ ghi lúc trạng thái ĐỔI (transition không
None), không ghi mỗi frame — tránh phình log, và để mỗi dòng có ý nghĩa
"vừa xảy ra 1 lần chuyển trạng thái" khi vẽ biểu đồ trạng thái theo thời gian
cho luận văn.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from .signal_state_machine import StateTransition


class StateTransitionLogger:
    def __init__(self, log_path: Union[str, Path]) -> None:
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "a", encoding="utf-8")

    def log(self, transition: StateTransition) -> None:
        record = {
            "timestamp": transition.timestamp,
            "scope": transition.scope,
            "from_state": transition.from_state,
            "to_state": transition.to_state,
        }
        if transition.signal_name is not None:
            record["signal_name"] = transition.signal_name
        # scope="signal" -> exceed_ratio; scope="session" -> risk_score (xem
        # 2 dòng ví dụ khác nhau ở docs/DATA_SCHEMAS.md mục 4).
        if transition.exceed_ratio is not None:
            record["exceed_ratio"] = transition.exceed_ratio
        if transition.risk_score is not None:
            record["risk_score"] = transition.risk_score
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()  # phục vụ debug/demo real-time - muốn thấy log ngay khi vừa ghi

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def __enter__(self) -> "StateTransitionLogger":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
