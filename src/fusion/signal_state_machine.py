"""SignalStateMachine — trạng thái NORMAL/SUSPICIOUS/ALERT cho MỘT tín hiệu,
theo sliding window + hysteresis 2 cấp (docs/DIAGRAMS.md mục 3.1, Tuần 9).

Khác bản tham khảo (chỉ ghi 1 loại vi phạm/frame theo if/elif ưu tiên, loại
trừ lẫn nhau, bỏ sót khi nhiều tín hiệu vượt ngưỡng cùng lúc): ở đây MỖI
signal_name có 1 instance `SignalStateMachine` riêng, hoàn toàn không biết
đến state machine của signal khác — xem `SignalStateTracker` (tracker.py) là
nơi giữ nhiều instance này ĐỘC LẬP, không có nhánh loại trừ nào giữa chúng.

`IDENTITY` không cần xử lý ngoại lệ riêng ở đây dù chỉ re-verify mỗi
~30s (docs/DIAGRAMS.md mục 3.1 ghi chú "carry-forward"): `IdentitySignal.
process()` đã tự trả lại NGUYÊN `SignalResult` của lần verify gần nhất ở
những frame không verify (xem src/signals/identity.py), nên exceeds_threshold
đưa vào sliding window ở đây tự nhiên lặp lại đúng giá trị carry-forward —
không cần nhánh code riêng cho IDENTITY.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque, Optional, Tuple

from src.signals.base import SignalResult


class SignalState(str, Enum):
    NORMAL = "NORMAL"
    SUSPICIOUS = "SUSPICIOUS"
    ALERT = "ALERT"


@dataclass(frozen=True)
class StateTransition:
    """1 lần đổi trạng thái — khớp định dạng `state_transitions.jsonl`
    (docs/DATA_SCHEMAS.md mục 4). `signal_name` là None cho transition ở
    `scope="session"` (tầng tổng hợp, Tuần 10, xem `session.py`).

    Chỉ 1 trong 2 field `exceed_ratio`/`risk_score` được set tuỳ `scope` —
    đúng 2 dòng ví dụ khác nhau ở docs/DATA_SCHEMAS.md mục 4
    (`scope="signal"` có `exceed_ratio`, `scope="session"` có `risk_score`)."""

    timestamp: float
    scope: str  # "signal" | "session"
    signal_name: Optional[str]
    from_state: str
    to_state: str
    exceed_ratio: Optional[float] = None  # chỉ set khi scope="signal"
    risk_score: Optional[float] = None  # chỉ set khi scope="session"


class SignalStateMachine:
    """State machine của 1 signal. `exceed_ratio` = tỉ lệ frame có
    `exceeds_threshold=True` trong cửa sổ trượt `window_sec` gần nhất.

    Hysteresis 2 cấp, đúng thiết kế mục 3.1 DIAGRAMS.md: ALERT chỉ thoát về
    SUSPICIOUS (không nhảy thẳng ALERT->NORMAL), và ngưỡng ra luôn thấp hơn
    ngưỡng vào ở mỗi cấp — chống dao động khi exceed_ratio lơ lửng quanh 1
    ngưỡng duy nhất.
    """

    def __init__(
        self,
        signal_name: str,
        window_sec: float = 4.0,
        r_enter_susp: float = 0.3,
        r_exit_susp: float = 0.15,
        r_enter_alert: float = 0.6,
        r_exit_alert: float = 0.4,
    ) -> None:
        if window_sec <= 0:
            raise ValueError("window_sec phải > 0")
        if not 0.0 <= r_exit_susp < r_enter_susp <= 1.0:
            raise ValueError("cần 0 <= r_exit_susp < r_enter_susp <= 1")
        if not 0.0 <= r_exit_alert < r_enter_alert <= 1.0:
            raise ValueError("cần 0 <= r_exit_alert < r_enter_alert <= 1")
        if r_enter_susp > r_enter_alert:
            raise ValueError("r_enter_susp phải <= r_enter_alert")

        self.signal_name = signal_name
        self._window_sec = window_sec
        self._r_enter_susp = r_enter_susp
        self._r_exit_susp = r_exit_susp
        self._r_enter_alert = r_enter_alert
        self._r_exit_alert = r_exit_alert

        self._history: Deque[Tuple[float, bool]] = deque()
        self._state = SignalState.NORMAL

    @property
    def state(self) -> SignalState:
        return self._state

    def reset(self) -> None:
        self._history.clear()
        self._state = SignalState.NORMAL

    def _push_and_trim(self, now: float, exceeds: bool) -> None:
        self._history.append((now, exceeds))
        while self._history and (now - self._history[0][0]) > self._window_sec:
            self._history.popleft()

    def _exceed_ratio(self) -> float:
        if not self._history:
            return 0.0
        return sum(1 for _, exceeds in self._history if exceeds) / len(self._history)

    def update(self, result: SignalResult) -> Tuple[SignalState, float, Optional[StateTransition]]:
        """Nạp 1 `SignalResult` mới của ĐÚNG signal này (không kiểm tra
        `signal_name` khớp — trách nhiệm khớp tên là của `SignalStateTracker`).

        Trả về (trạng thái hiện tại sau khi cập nhật, exceed_ratio, transition
        vừa xảy ra hoặc None nếu trạng thái không đổi)."""
        self._push_and_trim(result.timestamp, result.exceeds_threshold)
        ratio = self._exceed_ratio()

        new_state = self._state
        if self._state is SignalState.NORMAL:
            if ratio >= self._r_enter_susp:
                new_state = SignalState.SUSPICIOUS
        elif self._state is SignalState.SUSPICIOUS:
            if ratio >= self._r_enter_alert:
                new_state = SignalState.ALERT
            elif ratio <= self._r_exit_susp:
                new_state = SignalState.NORMAL
        else:  # ALERT — chỉ thoát qua SUSPICIOUS
            if ratio <= self._r_exit_alert:
                new_state = SignalState.SUSPICIOUS

        transition: Optional[StateTransition] = None
        if new_state is not self._state:
            transition = StateTransition(
                timestamp=result.timestamp,
                scope="signal",
                signal_name=self.signal_name,
                from_state=self._state.value,
                to_state=new_state.value,
                exceed_ratio=round(ratio, 4),
            )
            self._state = new_state

        return self._state, ratio, transition
