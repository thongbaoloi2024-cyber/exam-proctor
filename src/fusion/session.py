"""SessionHysteresis — hysteresis 2 ngưỡng ở TẦNG PHIÊN (docs/DIAGRAMS.md
mục 3.2, Tuần 10): SESSION_NORMAL <-> SESSION_ALERT dựa trực tiếp trên giá
trị `risk_score` TỨC THỜI của frame hiện tại.

KHÁC `SignalStateMachine` (Tuần 9, `signal_state_machine.py`): state machine
per-signal tính trên `exceed_ratio` gộp qua 1 CỬA SỔ TRƯỢT theo thời gian
(chống nhiễu tức thời của 1 tín hiệu thô). Ở tầng phiên, `risk_score` đã LÀ
kết quả tổng hợp của các state machine per-signal (vốn đã ổn định qua cửa sổ
trượt riêng của từng signal) — không cần trượt cửa sổ thêm 1 lần nữa ở đây,
chỉ cần Schmitt trigger kinh điển (ngưỡng vào cao hơn ngưỡng ra) để chặn dao
động khi risk_score lơ lửng quanh 1 ngưỡng duy nhất.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple

from .signal_state_machine import StateTransition


class SessionState(str, Enum):
    SESSION_NORMAL = "SESSION_NORMAL"
    SESSION_ALERT = "SESSION_ALERT"


class SessionHysteresis:
    def __init__(self, t_enter: float, t_exit: float) -> None:
        if not t_exit < t_enter:
            raise ValueError("cần T_exit < T_enter (hysteresis)")
        self._t_enter = t_enter
        self._t_exit = t_exit
        self._state = SessionState.SESSION_NORMAL

    @property
    def state(self) -> SessionState:
        return self._state

    def reset(self) -> None:
        self._state = SessionState.SESSION_NORMAL

    def update(self, risk_score: float, timestamp: float) -> Tuple[SessionState, Optional[StateTransition]]:
        """Cập nhật với `risk_score` của frame hiện tại, trả về (trạng thái
        phiên sau khi cập nhật, transition nếu vừa đổi trạng thái else
        None). Rising edge (SESSION_NORMAL -> SESSION_ALERT) là thời điểm
        sinh `ViolationEvent` (xem `engine.py`)."""
        new_state = self._state
        if self._state is SessionState.SESSION_NORMAL:
            if risk_score >= self._t_enter:
                new_state = SessionState.SESSION_ALERT
        else:  # SESSION_ALERT
            if risk_score <= self._t_exit:
                new_state = SessionState.SESSION_NORMAL

        transition: Optional[StateTransition] = None
        if new_state is not self._state:
            transition = StateTransition(
                timestamp=timestamp,
                scope="session",
                signal_name=None,
                from_state=self._state.value,
                to_state=new_state.value,
                risk_score=round(risk_score, 4),
            )
            self._state = new_state

        return self._state, transition
