"""Signal package with lazy public exports.

Keeping ``__init__`` lightweight lets the web/reporting backend import the
shared schemas without initializing MediaPipe, PyTorch, or Ultralytics.
"""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "SignalExtractor": ("src.signals.base", "SignalExtractor"),
    "SignalResult": ("src.signals.base", "SignalResult"),
    "FacePresenceSignal": ("src.signals.face_presence", "FacePresenceSignal"),
    "MultiFaceSignal": ("src.signals.multi_face", "MultiFaceSignal"),
    "EyeStateSignal": ("src.signals.eye_state", "EyeStateSignal"),
    "MouthStateSignal": ("src.signals.mouth_state", "MouthStateSignal"),
    "ObjectSignal": ("src.signals.object_signal", "ObjectSignal"),
    "HeadPoseSignal": ("src.signals.head_pose", "HeadPoseSignal"),
    "IdentitySignal": ("src.signals.identity", "IdentitySignal"),
    "BlinkLivenessChallenge": ("src.signals.liveness", "BlinkLivenessChallenge"),
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
