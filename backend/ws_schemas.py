"""Strict schemas for data accepted from the untrusted desktop client."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SignalName = Literal[
    "FACE_PRESENCE",
    "MULTI_FACE",
    "EYE_STATE",
    "MOUTH_STATE",
    "OBJECT_PRESENCE",
    "HEAD_POSE",
    "IDENTITY",
]
EXPECTED_SIGNAL_NAMES = {
    "FACE_PRESENCE", "MULTI_FACE", "EYE_STATE", "MOUTH_STATE",
    "OBJECT_PRESENCE", "HEAD_POSE", "IDENTITY",
}
SignalState = Literal["NORMAL", "SUSPICIOUS", "ALERT"]
SessionState = Literal["SESSION_NORMAL", "SESSION_ALERT"]
ViolationType = Literal[
    "FACE_ABSENT",
    "MULTIPLE_FACES",
    "EYES_CLOSED",
    "GAZE_AWAY",  # read compatibility for logs created before v2
    "TALKING",
    "OBJECT_DETECTED",
    "HEAD_POSE_AWAY",
    "IDENTITY_MISMATCH",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _finite(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("Gia tri phai huu han")
    return value


class SignalResultData(StrictModel):
    signal_name: SignalName
    timestamp: float
    value: float
    exceeds_threshold: bool
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp", "value")
    @classmethod
    def finite_numbers(cls, value: float) -> float:
        return _finite(value)


class RiskUpdateData(StrictModel):
    risk_score: float = Field(ge=0.0, le=100.0)
    session_state: SessionState
    video_time_sec: float = Field(ge=0.0, le=48 * 60 * 60)
    timestamp: float

    @field_validator("risk_score", "video_time_sec", "timestamp")
    @classmethod
    def finite_numbers(cls, value: float) -> float:
        return _finite(value)


class TelemetryUpdateData(RiskUpdateData):
    signals: List[SignalResultData] = Field(default_factory=list, max_length=16)
    signal_states: Dict[SignalName, SignalState]

    @model_validator(mode="after")
    def unique_signal_names(self) -> "TelemetryUpdateData":
        names = [result.signal_name for result in self.signals]
        if len(names) != len(set(names)):
            raise ValueError("Moi signal chi duoc xuat hien mot lan trong telemetry_update")
        if set(names) != EXPECTED_SIGNAL_NAMES or set(self.signal_states) != EXPECTED_SIGNAL_NAMES:
            raise ValueError("telemetry_update phai chua du 7 signal va 7 state")
        return self


class SnapshotUpload(StrictModel):
    content_type: Literal["image/jpeg", "image/png"]
    data_base64: str = Field(min_length=4, max_length=3_000_000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ContributingSignalData(StrictModel):
    signal_name: SignalName
    violation_type: ViolationType
    state: Literal["SUSPICIOUS", "ALERT"]
    value: float
    weight: float = Field(ge=0.0, le=20.0)

    @field_validator("value", "weight")
    @classmethod
    def finite_numbers(cls, value: float) -> float:
        return _finite(value)


class ViolationEventData(StrictModel):
    event_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    session_id: str = Field(min_length=1, max_length=64)
    video_time_sec: float = Field(ge=0.0, le=48 * 60 * 60)
    timestamp: datetime
    risk_score: float = Field(ge=0.0, le=100.0)
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    primary_violation: ViolationType
    contributing_signals: List[ContributingSignalData] = Field(default_factory=list, max_length=16)
    # Kept as a null-only compatibility field because the local dataclass has
    # this key.  A client-controlled filesystem path is never accepted.
    snapshot_path: None = None
    snapshot: Optional[SnapshotUpload] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("video_time_sec", "risk_score")
    @classmethod
    def finite_numbers(cls, value: float) -> float:
        return _finite(value)

    @field_validator("timestamp")
    @classmethod
    def timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp phai kem mui gio")
        return value

    @model_validator(mode="after")
    def unique_contributing_signals(self) -> "ViolationEventData":
        names = [item.signal_name for item in self.contributing_signals]
        if not names or len(names) != len(set(names)):
            raise ValueError("contributing_signals phai khac rong va khong trung signal")
        return self


class EndSessionData(StrictModel):
    reason: Literal[
        "completed",
        "enrollment_failed",
        "client_shutdown",
        "monitor_closed",
        "permission_denied",
    ] = "completed"


class HeartbeatData(StrictModel):
    timestamp: float

    @field_validator("timestamp")
    @classmethod
    def finite_timestamp(cls, value: float) -> float:
        return _finite(value)


BrowserEventType = Literal[
    "CONTENT_MONITOR_READY",
    "TAB_HIDDEN",
    "TAB_VISIBLE",
    "WINDOW_BLUR",
    "WINDOW_FOCUS",
    "TAB_SWITCHED",
    "NEW_TAB",
    "NAVIGATION_AWAY",
    "FULLSCREEN_EXIT",
    "FULLSCREEN_ENTER",
    "CLIPBOARD_COPY",
    "CLIPBOARD_PASTE",
    "CONTEXT_MENU",
    "CAMERA_MUTED",
    "CAMERA_ENDED",
    "MICROPHONE_MUTED",
    "MICROPHONE_ENDED",
    "SCREEN_SHARE_ENDED",
    "MONITOR_CLOSED",
    "PERMISSION_MISSING",
]


class ClientHelloData(StrictModel):
    extension_version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$", max_length=32)
    browser_name: str = Field(min_length=1, max_length=50)
    browser_version: Optional[str] = Field(default=None, max_length=50)
    platform: Optional[str] = Field(default=None, max_length=100)
    device_id: UUID
    capabilities: List[Literal[
        "camera", "microphone", "screen_share", "content_monitor", "storage_session",
    ]] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def unique_capabilities(self) -> "ClientHelloData":
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("capabilities khong duoc trung")
        return self


class BrowserEventData(StrictModel):
    event_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    sequence: int = Field(ge=0, le=2_147_483_647)
    event_type: BrowserEventType
    client_timestamp: datetime
    observed_origin: Optional[str] = Field(default=None, max_length=255)
    duration_ms: Optional[int] = Field(default=None, ge=0, le=24 * 60 * 60 * 1000)
    snapshot: Optional[SnapshotUpload] = None
    metadata: Dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("client_timestamp")
    @classmethod
    def browser_timestamp_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("client_timestamp phai kem mui gio")
        return value

    @field_validator("observed_origin")
    @classmethod
    def origin_only(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.netloc
            or parts.username
            or parts.password
            or parts.path not in {"", "/"}
            or parts.query
            or parts.fragment
        ):
            raise ValueError("Chi duoc gui origin HTTP(S), khong gui query/fragment")
        return f"{parts.scheme}://{parts.netloc}"

    @field_validator("metadata")
    @classmethod
    def small_scalar_metadata(cls, value: Dict[str, str | int | float | bool]):
        if len(value) > 8 or any(len(str(key)) > 40 or len(str(item)) > 200 for key, item in value.items()):
            raise ValueError("metadata vuot gioi han")
        for item in value.values():
            if isinstance(item, float):
                _finite(item)
        return value


MESSAGE_DATA_MODELS = {
    "telemetry_update": TelemetryUpdateData,
    "violation_event": ViolationEventData,
    "end_session": EndSessionData,
    "heartbeat": HeartbeatData,
    "client_hello": ClientHelloData,
    "browser_event": BrowserEventData,
}
