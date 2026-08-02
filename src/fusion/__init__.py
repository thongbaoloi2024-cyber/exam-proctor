"""Risk-fusion package with lazy public exports."""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "SessionThresholds": ("src.fusion.config", "SessionThresholds"),
    "load_session_thresholds": ("src.fusion.config", "load_session_thresholds"),
    "load_signal_state_machines": ("src.fusion.config", "load_signal_state_machines"),
    "load_signal_weights": ("src.fusion.config", "load_signal_weights"),
    "RiskFusionEngine": ("src.fusion.engine", "RiskFusionEngine"),
    "RiskScoreLogger": ("src.fusion.risk_score_logger", "RiskScoreLogger"),
    "SessionHysteresis": ("src.fusion.session", "SessionHysteresis"),
    "SessionState": ("src.fusion.session", "SessionState"),
    "SignalState": ("src.fusion.signal_state_machine", "SignalState"),
    "SignalStateMachine": ("src.fusion.signal_state_machine", "SignalStateMachine"),
    "StateTransition": ("src.fusion.signal_state_machine", "StateTransition"),
    "StateTransitionLogger": ("src.fusion.state_transition_logger", "StateTransitionLogger"),
    "SignalStateTracker": ("src.fusion.tracker", "SignalStateTracker"),
    "VIOLATION_TYPE_BY_SIGNAL": ("src.fusion.violation_event", "VIOLATION_TYPE_BY_SIGNAL"),
    "ContributingSignal": ("src.fusion.violation_event", "ContributingSignal"),
    "ViolationEvent": ("src.fusion.violation_event", "ViolationEvent"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value
