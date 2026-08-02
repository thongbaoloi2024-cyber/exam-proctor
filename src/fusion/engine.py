"""RiskFusionEngine — tầng tổng hợp cuối cùng (Tuần 10, docs/DIAGRAMS.md mục
3.2): gộp trạng thái của toàn bộ per-signal state machine (Tuần 9,
`signal_state_machine.py`/`tracker.py`) thành 1 `risk_score` có trọng số,
áp dụng hysteresis 2 ngưỡng Ở TẦNG PHIÊN (`session.py`), và sinh
`ViolationEvent` đúng lúc `risk_score` vừa vượt `T_enter` (rising edge).

    risk_score = Σ_i ( weight_i × state_value_i )   state_value: NORMAL=0,
                                                     SUSPICIOUS=1, ALERT=2

`ViolationEvent` CHỈ sinh ở rising edge (SESSION_NORMAL -> SESSION_ALERT) —
không sinh lặp lại mỗi frame trong lúc đang SESSION_ALERT kéo dài, tránh log
bị ngập bởi cùng 1 vi phạm (đúng ghi chú thiết kế mục 2 DIAGRAMS.md).
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

import numpy as np

from src.signals.base import SignalResult

from .config import load_session_thresholds, load_signal_state_machines, load_signal_weights, resolve_severity_thresholds
from .risk_score_logger import RiskScoreLogger
from .session import SessionHysteresis, SessionState
from .signal_state_machine import SignalState
from .state_transition_logger import StateTransitionLogger
from .tracker import SignalStateTracker
from .violation_event import VIOLATION_TYPE_BY_SIGNAL, ContributingSignal, ViolationEvent

_STATE_VALUE: Dict[SignalState, int] = {
    SignalState.NORMAL: 0,
    SignalState.SUSPICIOUS: 1,
    SignalState.ALERT: 2,
}


class RiskFusionEngine:
    def __init__(
        self,
        tracker: SignalStateTracker,
        weights: Dict[str, float],
        t_enter: float,
        t_exit: float,
        session_id: str,
        session_start_ts: Optional[float] = None,
        severity_medium_min: Optional[float] = None,
        severity_high_min: Optional[float] = None,
        snapshot_dir: Optional[Union[str, Path]] = None,
        logger: Optional[StateTransitionLogger] = None,
        risk_score_logger: Optional[RiskScoreLogger] = None,
        fusion_config_version: str = "v1",
    ) -> None:
        self._tracker = tracker
        self._weights = dict(weights)
        self._session = SessionHysteresis(t_enter, t_exit)
        self._session_id = session_id
        self._session_start_ts = session_start_ts
        self._risk_score_logger = risk_score_logger
        # Cong thuc mac dinh (MEDIUM tu T_enter, HIGH o 2xT_enter) nam DUY
        # NHAT trong resolve_severity_thresholds() - dung chung voi
        # src/reporting/report_generator.py de bieu do severity khong bao
        # gio ve lech ngoi voi nhan severity that (xem docstring ham do).
        self._severity_medium_min, self._severity_high_min = resolve_severity_thresholds(
            t_enter, severity_medium_min, severity_high_min,
        )
        self._snapshot_dir = Path(snapshot_dir) if snapshot_dir else None
        if self._snapshot_dir is not None:
            self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logger
        self._fusion_config_version = fusion_config_version

        self._last_results: Dict[str, SignalResult] = {}
        self._last_risk_score: float = 0.0

    @classmethod
    def from_config(
        cls,
        config_path: Union[str, Path],
        session_id: str,
        session_start_ts: Optional[float] = None,
        snapshot_dir: Optional[Union[str, Path]] = None,
        logger: Optional[StateTransitionLogger] = None,
        risk_score_logger: Optional[RiskScoreLogger] = None,
        fusion_config_version: str = "v1",
    ) -> "RiskFusionEngine":
        """Dựng engine đầy đủ từ 1 file YAML duy nhất (docs/DATA_SCHEMAS.md
        mục 6) — nơi duy nhất ghép `SignalStateTracker` (Tuần 9) với trọng
        số + ngưỡng phiên (Tuần 10) đọc từ cùng 1 config, tránh 2 nơi phải tự
        đồng bộ thủ công."""
        machines = load_signal_state_machines(config_path)
        weights = load_signal_weights(config_path)
        thresholds = load_session_thresholds(config_path)
        tracker = SignalStateTracker(machines, logger=logger)
        return cls(
            tracker=tracker,
            weights=weights,
            t_enter=thresholds.t_enter,
            t_exit=thresholds.t_exit,
            session_id=session_id,
            session_start_ts=session_start_ts,
            severity_medium_min=thresholds.severity_medium_min,
            severity_high_min=thresholds.severity_high_min,
            snapshot_dir=snapshot_dir,
            logger=logger,
            risk_score_logger=risk_score_logger,
            fusion_config_version=fusion_config_version,
        )

    @property
    def tracker(self) -> SignalStateTracker:
        return self._tracker

    @property
    def session_state(self) -> SessionState:
        return self._session.state

    @property
    def last_risk_score(self) -> float:
        return self._last_risk_score

    def reset(self, session_start_ts: Optional[float] = None) -> None:
        self._tracker.reset()
        self._session.reset()
        self._last_results.clear()
        self._last_risk_score = 0.0
        self._session_start_ts = session_start_ts

    def _risk_score(self) -> float:
        total = 0.0
        for signal_name, state in self._tracker.states().items():
            weight = self._weights.get(signal_name, 0.0)
            total += weight * _STATE_VALUE[state]
        return total

    def _severity(self, risk_score: float) -> str:
        if risk_score >= self._severity_high_min:
            return "HIGH"
        if risk_score >= self._severity_medium_min:
            return "MEDIUM"
        return "LOW"

    def _contributing_signals(self) -> List[ContributingSignal]:
        contributing = []
        for signal_name, state in self._tracker.states().items():
            if state is SignalState.NORMAL:
                continue
            result = self._last_results.get(signal_name)
            contributing.append(
                ContributingSignal(
                    signal_name=signal_name,
                    violation_type=VIOLATION_TYPE_BY_SIGNAL.get(signal_name, signal_name),
                    state=state.value,
                    value=result.value if result is not None else 0.0,
                    weight=self._weights.get(signal_name, 0.0),
                )
            )
        return contributing

    @staticmethod
    def _primary_violation(contributing: List[ContributingSignal]) -> str:
        """Signal có (weight x state_value) cao nhất, đúng thiết kế mục 3
        DATA_SCHEMAS.md - ưu tiên tự nhiên các signal đang ALERT (state_value
        =2) hơn SUSPICIOUS (state_value=1) qua phép nhân. Vẫn xử lý được ca
        biên "risk_score vượt T_enter chỉ nhờ nhiều signal SUSPICIOUS cộng
        dồn, chưa signal nào ALERT" - vẫn chọn được 1 primary hợp lý thay vì
        lỗi/rỗng."""
        state_value = {"ALERT": 2, "SUSPICIOUS": 1}
        return max(contributing, key=lambda c: c.weight * state_value[c.state]).violation_type

    def _save_snapshot(self, event_id: str, frame_bgr: Optional[np.ndarray]) -> Optional[str]:
        if frame_bgr is None or self._snapshot_dir is None:
            return None
        import cv2  # import cuc bo - chi can khi thuc su co frame de luu

        path = self._snapshot_dir / f"evt_{event_id[:8]}.jpg"
        cv2.imwrite(str(path), frame_bgr)
        return str(path)

    def update(
        self,
        results: Iterable[SignalResult],
        frame_bgr: Optional[np.ndarray] = None,
    ) -> Optional[ViolationEvent]:
        """Nạp `SignalResult` của 1 frame (cập nhật TOÀN BỘ per-signal state
        machine bên trong `tracker`), tính `risk_score`, cập nhật hysteresis
        phiên, và trả `ViolationEvent` nếu đây là rising edge SESSION_NORMAL
        -> SESSION_ALERT (None nếu không có event nào sinh ra)."""
        results = list(results)
        for result in results:
            self._last_results[result.signal_name] = result

        self._tracker.update(results)
        risk_score = self._risk_score()
        self._last_risk_score = risk_score

        now = results[0].timestamp if results else time.time()
        if self._session_start_ts is None:
            self._session_start_ts = now

        session_state, transition = self._session.update(risk_score, now)
        if transition is not None and self._logger is not None:
            self._logger.log(transition)
        if self._risk_score_logger is not None:
            self._risk_score_logger.log(
                timestamp=now,
                video_time_sec=now - self._session_start_ts,
                risk_score=risk_score,
                session_state=session_state.value,
            )

        if transition is None or transition.to_state != SessionState.SESSION_ALERT.value:
            return None

        contributing = self._contributing_signals()
        event_id = str(uuid.uuid4())
        event = ViolationEvent(
            event_id=event_id,
            session_id=self._session_id,
            video_time_sec=round(now - self._session_start_ts, 3),
            # fromtimestamp(..., tz=utc).astimezone() thay vi fromtimestamp(now)
            # tran (naive) roi moi .astimezone(): ban naive goi thang localtime()
            # cua he dieu hanh tren epoch truyen vao, tren Windows ham nay bao
            # loi OSError voi epoch nho/gan 1970 (VD cac gia tri float nho dung
            # trong unit test) sau khi tru lech mui gio am - duong tren tranh
            # goi localtime() truc tiep tren epoch, chi convert qua object
            # datetime co san nen khong con van de nay (van dung timestamp
            # epoch that tu time.time() o production).
            timestamp=datetime.fromtimestamp(now, tz=timezone.utc).astimezone().isoformat(timespec="milliseconds"),
            risk_score=round(risk_score, 3),
            severity=self._severity(risk_score),
            primary_violation=self._primary_violation(contributing),
            contributing_signals=contributing,
            snapshot_path=self._save_snapshot(event_id, frame_bgr),
            metadata={"fusion_config_version": self._fusion_config_version},
        )
        return event
