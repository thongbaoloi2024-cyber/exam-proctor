"""build_signals_from_config(config_path) -> Dict[str, SignalExtractor] -
thay the hoan toan `_build_other_signals()` + dong `IdentitySignal(...)`
hardcode truoc day trong main.py (Tuan 4-6) bang cach doc tham so dung tu
chinh `config/fusion.yaml` (Tuan 13).

Sua dung bug that da xac nhan (docs/KE_HOACH_CHI_TIET_TUAN12.md muc 0):
main.py cu hardcode `cosine_threshold_warn=0.60`/`cosine_threshold_alert=0.45`
cho IdentitySignal, khac han YAML khai `0.55`/`0.40` - ke tu day YAML la
nguon su that duy nhat.

Tra ve `Dict` (khong phai `List`) de `AppController` lay rieng
`signals["IDENTITY"]` cho buoc enrollment ma khong can lap tim.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Union

import yaml

from .base import SignalExtractor
from .eye_state import EyeStateSignal
from .face_presence import FacePresenceSignal
from .head_pose import HeadPoseSignal
from .identity import IdentitySignal
from .mouth_state import MouthStateSignal
from .multi_face import MultiFaceSignal
from .object_signal import ObjectSignal


def build_signals_from_config(
    config_path: Union[str, Path] = "config/fusion.yaml",
) -> Dict[str, SignalExtractor]:
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    signals_cfg = raw.get("signals") or {}

    def _cfg(name: str) -> dict:
        return signals_cfg.get(name) or {}

    face_presence_cfg = _cfg("FACE_PRESENCE")
    multi_face_cfg = _cfg("MULTI_FACE")
    eye_state_cfg = _cfg("EYE_STATE")
    mouth_state_cfg = _cfg("MOUTH_STATE")
    object_cfg = _cfg("OBJECT_PRESENCE")
    head_pose_cfg = _cfg("HEAD_POSE")
    identity_cfg = _cfg("IDENTITY")

    return {
        "FACE_PRESENCE": FacePresenceSignal(
            absence_threshold_sec=face_presence_cfg.get("absence_threshold_sec", 2.0),
        ),
        "MULTI_FACE": MultiFaceSignal(
            confidence_threshold=multi_face_cfg.get("confidence_threshold", 0.90),
        ),
        "EYE_STATE": EyeStateSignal(
            ear_threshold=eye_state_cfg.get("ear_threshold", 0.21),
            min_closed_duration_sec=eye_state_cfg.get("min_closed_duration_sec", 1.0),
        ),
        "MOUTH_STATE": MouthStateSignal(
            open_ratio_threshold=mouth_state_cfg.get("open_ratio_threshold", 0.15),
            activity_window_sec=mouth_state_cfg.get("activity_window_sec", 2.0),
            activity_ratio_threshold=mouth_state_cfg.get("activity_ratio_threshold", 0.25),
            min_window_coverage_sec=mouth_state_cfg.get("min_window_coverage_sec", 1.0),
        ),
        "OBJECT_PRESENCE": ObjectSignal(
            min_present_duration_sec=object_cfg.get("min_present_duration_sec", 1.0),
        ),
        "HEAD_POSE": HeadPoseSignal(
            yaw_threshold_deg=head_pose_cfg.get("yaw_threshold_deg", 20.0),
            pitch_threshold_deg=head_pose_cfg.get("pitch_threshold_deg", 20.0),
            min_away_duration_sec=head_pose_cfg.get("min_away_duration_sec", 1.0),
        ),
        "IDENTITY": IdentitySignal(
            reverify_interval_sec=identity_cfg.get("reverify_interval_sec", 30.0),
            cosine_threshold_warn=identity_cfg.get("cosine_threshold_warn", 0.60),
            cosine_threshold_alert=identity_cfg.get("cosine_threshold_alert", 0.45),
            consecutive_failures_required=identity_cfg.get("consecutive_failures_required", 2),
        ),
    }
