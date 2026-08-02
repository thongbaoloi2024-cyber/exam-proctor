"""SignalStateTracker — quản lý N `SignalStateMachine` ĐỘC LẬP (1 cho mỗi
signal_name), điểm khác biệt cốt lõi so với bản tham khảo (chỉ ghi 1 loại vi
phạm/frame theo if/elif ưu tiên, loại trừ lẫn nhau, bỏ sót khi nhiều tín hiệu
vượt ngưỡng cùng lúc).

`update()` lặp qua TẤT CẢ `SignalResult` của 1 frame và cập nhật machine
tương ứng — KHÔNG có nhánh so sánh/loại trừ nào giữa các signal (không có
if/elif chọn 1 signal "ưu tiên nhất"), nên nhiều signal hoàn toàn có thể cùng
ở ALERT đồng thời (xem tests/test_signal_state_tracker.py).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from src.signals.base import SignalResult

from .signal_state_machine import SignalState, SignalStateMachine, StateTransition
from .state_transition_logger import StateTransitionLogger


class SignalStateTracker:
    def __init__(
        self,
        machines: Iterable[SignalStateMachine],
        logger: Optional[StateTransitionLogger] = None,
    ) -> None:
        self._machines: Dict[str, SignalStateMachine] = {m.signal_name: m for m in machines}
        self._logger = logger

    def reset(self) -> None:
        for machine in self._machines.values():
            machine.reset()

    def states(self) -> Dict[str, SignalState]:
        """Trạng thái hiện tại của mọi signal - dùng để đọc nhanh (VD overlay
        UI) mà không cần đợi transition mới."""
        return {name: machine.state for name, machine in self._machines.items()}

    def alerting_signals(self) -> List[str]:
        """Danh sách signal_name ĐANG ở ALERT tại thời điểm gọi — có thể có
        nhiều hơn 1 phần tử cùng lúc (đây chính là điểm khác bản tham khảo)."""
        return [name for name, machine in self._machines.items() if machine.state is SignalState.ALERT]

    def update(self, results: Iterable[SignalResult]) -> List[StateTransition]:
        """Cập nhật machine tương ứng cho từng `SignalResult`, ĐỘC LẬP với
        nhau, trả về danh sách transition vừa xảy ra ở frame này (rỗng nếu
        không signal nào đổi trạng thái). `SignalResult` có `signal_name`
        không khớp machine nào đã đăng ký (VD chưa cấu hình ngưỡng) sẽ bị bỏ
        qua thay vì lỗi, để tracker không phụ thuộc phải cấu hình đủ 7/7."""
        transitions: List[StateTransition] = []
        for result in results:
            machine = self._machines.get(result.signal_name)
            if machine is None:
                continue
            _, _, transition = machine.update(result)
            if transition is not None:
                transitions.append(transition)
                if self._logger is not None:
                    self._logger.log(transition)
        return transitions
