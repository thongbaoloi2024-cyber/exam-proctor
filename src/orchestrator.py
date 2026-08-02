"""PipelineOrchestrator — chạy PerceptionLayer + toàn bộ SignalExtractor mỗi
frame, thu thập kết quả thành 1 danh sách `SignalResult` thống nhất, đo hiệu
năng từng bước, log ra console/file, và (Tuần 9) cập nhật Risk Fusion Engine
(per-signal state machine) nếu được truyền vào.

Tuần 7: đây là bước trung gian, thay thế phần "gọi perception + lặp qua từng
signal" mà `main.py` trước đó tự viết tay, để logic này chỉ tồn tại ở 1 chỗ
(main.py, script benchmark, và sau này script đánh giá Tuần 14 đều dùng chung
class này thay vì mỗi nơi tự lặp lại).

Tuần 9: nhận thêm `state_tracker` (SignalStateTracker) tuỳ chọn — nếu có,
`process_frame` sẽ cập nhật state machine của TỪNG signal ngay sau khi có
`SignalResult`, và các transition (nếu có) được lưu lại qua `last_transitions`
để `main.py`/script khác đọc mà không cần đổi signature `process_frame`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, IO, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from src.fusion.signal_state_machine import StateTransition
from src.fusion.tracker import SignalStateTracker
from src.perception.perception_result import PerceptionResult
from src.perception.preprocessor import PreprocessedFrame
from src.signals.base import SignalExtractor, SignalResult

if TYPE_CHECKING:
    # PerceptionLayer imports every model backend (MTCNN, MediaPipe and
    # Ultralytics).  It is needed here only for static typing; importing it at
    # runtime made lightweight consumers such as the backend and unit tests
    # require the complete CV stack even when they inject a fake perception
    # implementation.
    from src.perception.pipeline import PerceptionLayer


class PipelineOrchestrator:
    def __init__(
        self,
        perception: PerceptionLayer,
        signals: Sequence[SignalExtractor],
        log_path: Optional[Union[str, Path]] = None,
        state_tracker: Optional[SignalStateTracker] = None,
    ) -> None:
        self._perception = perception
        self._signals = list(signals)
        self._log_file: Optional[IO[str]] = open(log_path, "a", encoding="utf-8") if log_path else None
        self._state_tracker = state_tracker
        self._last_transitions: List[StateTransition] = []

        self._frame_count = 0
        self._timing_totals: Dict[str, float] = {}

    def process_frame(
        self, raw_frame_bgr: np.ndarray
    ) -> Tuple[PreprocessedFrame, PerceptionResult, List[SignalResult]]:
        preprocessed, perception_result = self._perception.process(raw_frame_bgr)

        results: List[SignalResult] = []
        for signal in self._signals:
            t0 = time.perf_counter()
            result = signal.process(perception_result)
            elapsed = time.perf_counter() - t0
            self._timing_totals[signal.signal_name] = self._timing_totals.get(signal.signal_name, 0.0) + elapsed
            results.append(result)

        for step, seconds in self._perception.last_timings.items():
            key = f"perception.{step}"
            self._timing_totals[key] = self._timing_totals.get(key, 0.0) + seconds

        self._frame_count += 1
        self._log(perception_result.timestamp, results)

        self._last_transitions = self._state_tracker.update(results) if self._state_tracker is not None else []

        return preprocessed, perception_result, results

    @property
    def last_transitions(self) -> List[StateTransition]:
        """Transition (per-signal state machine) vừa xảy ra ở lần
        `process_frame` gần nhất - rỗng nếu không cấu hình `state_tracker`
        hoặc không signal nào đổi trạng thái ở frame đó."""
        return self._last_transitions

    def _log(self, timestamp: float, results: List[SignalResult]) -> None:
        for result in results:
            if result.exceeds_threshold:
                print(f"[{result.signal_name}] VUOT NGUONG - {result.metadata}")
            if self._log_file is not None:
                line = json.dumps(
                    {
                        "timestamp": timestamp,
                        "signal_name": result.signal_name,
                        "value": result.value,
                        "exceeds_threshold": result.exceeds_threshold,
                        "confidence": result.confidence,
                    },
                    ensure_ascii=False,
                )
                self._log_file.write(line + "\n")

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def performance_report(self) -> Dict[str, float]:
        """Trả về số ms/frame trung bình cho từng bước (`perception.*` và
        từng signal theo `signal_name`) tính tới thời điểm gọi — dùng để tìm
        bottleneck (Tuần 7, xem scripts/benchmark_fps.py)."""
        if self._frame_count == 0:
            return {}
        return {
            name: (total_seconds / self._frame_count) * 1000.0
            for name, total_seconds in self._timing_totals.items()
        }

    def reset_all_signals(self) -> None:
        """Gọi reset() trên mọi signal VÀ mọi state machine (nếu có) — dùng
        khi bắt đầu 1 phiên giám sát mới, tránh state (bộ đếm thời gian,
        embedding tham chiếu, sliding window exceed_ratio...) của phiên
        trước rò rỉ sang phiên sau."""
        for signal in self._signals:
            signal.reset()
        if self._state_tracker is not None:
            self._state_tracker.reset()

    def close(self) -> None:
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None

    def __enter__(self) -> "PipelineOrchestrator":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
