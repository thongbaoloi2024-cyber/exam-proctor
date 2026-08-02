"""Đọc `config/fusion.yaml` (docs/DATA_SCHEMAS.md mục 6) thành các đối
tượng Risk Fusion Engine cần — tránh hardcode 4 ngưỡng hysteresis per-signal
(Tuần 9) VÀ trọng số + ngưỡng T_enter/T_exit/severity ở tầng phiên (Tuần 10)
rải rác trong code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import yaml

from .signal_state_machine import SignalStateMachine

_HYSTERESIS_KEYS = ("r_enter_susp", "r_exit_susp", "r_enter_alert", "r_exit_alert")


def _read_yaml(config_path: Union[str, Path]) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_signal_state_machines(
    config_path: Union[str, Path],
    window_sec: Optional[float] = None,
) -> List[SignalStateMachine]:
    """Tạo 1 `SignalStateMachine` cho mỗi signal khai báo đủ 4 ngưỡng
    hysteresis dưới mục `signals:` của YAML. Signal thiếu 1 trong 4 ngưỡng bị
    BỎ QUA (không lỗi) — cho phép YAML có mục signal chỉ cấu hình phần khác
    (VD tham số riêng của IdentitySignal) mà chưa cần state machine."""
    raw_config = _read_yaml(config_path)
    default_window = raw_config.get("window_sec", 4.0) if window_sec is None else window_sec

    machines: List[SignalStateMachine] = []
    for signal_name, signal_cfg in (raw_config.get("signals") or {}).items():
        if not all(key in signal_cfg for key in _HYSTERESIS_KEYS):
            continue
        machines.append(
            SignalStateMachine(
                signal_name=signal_name,
                window_sec=signal_cfg.get("window_sec", default_window),
                r_enter_susp=signal_cfg["r_enter_susp"],
                r_exit_susp=signal_cfg["r_exit_susp"],
                r_enter_alert=signal_cfg["r_enter_alert"],
                r_exit_alert=signal_cfg["r_exit_alert"],
            )
        )
    return machines


def load_signal_weights(config_path: Union[str, Path]) -> Dict[str, float]:
    """Đọc `weight` của từng signal dưới mục `signals:` — dùng cho
    `risk_score = Σ weight_i × state_value_i` (Tuần 10, docs/DIAGRAMS.md mục
    3.2). Signal không khai báo `weight` bị bỏ qua (coi như weight=0, không
    đóng góp vào risk_score, xử lý ở `RiskFusionEngine._risk_score`)."""
    raw_config = _read_yaml(config_path)
    return {
        signal_name: float(signal_cfg["weight"])
        for signal_name, signal_cfg in (raw_config.get("signals") or {}).items()
        if "weight" in signal_cfg
    }


@dataclass(frozen=True)
class SessionThresholds:
    t_enter: float
    t_exit: float
    severity_medium_min: Optional[float] = None
    severity_high_min: Optional[float] = None


def load_session_thresholds(config_path: Union[str, Path]) -> SessionThresholds:
    """Đọc ngưỡng T_enter/T_exit (hysteresis tầng phiên) và ngưỡng severity
    (LOW/MEDIUM/HIGH) dưới mục `session:` của YAML."""
    raw_config = _read_yaml(config_path)
    session_cfg = raw_config.get("session") or {}
    return SessionThresholds(
        t_enter=float(session_cfg["T_enter"]),
        t_exit=float(session_cfg["T_exit"]),
        severity_medium_min=(
            float(session_cfg["severity_medium_min"]) if "severity_medium_min" in session_cfg else None
        ),
        severity_high_min=(
            float(session_cfg["severity_high_min"]) if "severity_high_min" in session_cfg else None
        ),
    )


def resolve_severity_thresholds(
    t_enter: float,
    severity_medium_min: Optional[float] = None,
    severity_high_min: Optional[float] = None,
) -> Tuple[float, float]:
    """Áp mặc định 'MEDIUM bắt đầu từ T_enter, HIGH ở 2×T_enter' khi YAML
    không khai báo `severity_medium_min`/`severity_high_min` — dùng CHUNG bởi
    `RiskFusionEngine` (Tuần 10, quyết định severity thật của từng
    `ViolationEvent`) và `src/reporting/report_generator.py` (Tuần 11, vẽ
    vùng severity trên biểu đồ). Trước đây 2 nơi này tự tính lại cùng 1 công
    thức mặc định riêng — nếu 1 nơi sửa mà quên sửa nơi kia, biểu đồ có thể
    tô SAI vùng severity so với nhãn severity thật hiển thị cùng báo cáo
    (đúng lỗi "severity map lệch giữa module" cần tránh). Giờ chỉ có DUY
    NHẤT hàm này quyết định công thức mặc định."""
    medium_min = severity_medium_min if severity_medium_min is not None else t_enter
    high_min = severity_high_min if severity_high_min is not None else t_enter * 2.0
    return medium_min, high_min
