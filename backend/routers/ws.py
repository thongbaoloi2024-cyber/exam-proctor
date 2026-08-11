"""Authenticated WebSocket channels for desktop clients and dashboards.

Desktop tokens are carried in ``Authorization``. Browser extensions exchange
that token for a one-use 30-second ticket carried in ``Sec-WebSocket-Protocol``;
dashboard auth uses an HttpOnly cookie. Reusable credentials never enter a WS
URL. Every payload is untrusted and validated before persistence.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from .. import models
from ..auth import decode_session_websocket, decode_user_websocket
from ..authorization import Permission, authorize_exam
from ..candidate_tokens import hash_device_id
from ..db import SessionLocal
from ..session_materializer import (
    append_jsonl,
    browser_event_exists,
    build_session_meta,
    save_uploaded_snapshot,
    violation_event_exists,
    write_session_meta,
)
from ..ws_manager import manager
from ..ws_schemas import (
    BrowserEventData,
    ClientHelloData,
    MESSAGE_DATA_MODELS,
    TelemetryUpdateData,
    ViolationEventData,
)

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FUSION_CONFIG = _REPO_ROOT / "config" / "fusion.yaml"
_MAX_MESSAGE_CHARS = 4_100_000
_MAX_INVALID_MESSAGES = 3
_MAX_MESSAGES_PER_SECOND = 10


def _positive_float_env(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


_CLIENT_IDLE_TIMEOUT_SEC = _positive_float_env("CLIENT_IDLE_TIMEOUT_SEC", 20.0)


def _load_fusion_limits() -> tuple[float, float, float, float, float, dict[str, float]]:
    try:
        raw = yaml.safe_load(_FUSION_CONFIG.read_text(encoding="utf-8")) or {}
        signals = raw.get("signals") or {}
        weights = {name: float(cfg.get("weight", 0.0)) for name, cfg in signals.items()}
        max_risk = 2.0 * sum(weights.values())
        session = raw.get("session") or {}
        t_enter = float(session.get("T_enter", 5.0))
        return (
            max_risk,
            t_enter,
            float(session.get("T_exit", 2.5)),
            float(session.get("severity_medium_min", t_enter)),
            float(session.get("severity_high_min", 2.0 * t_enter)),
            weights,
        )
    except (OSError, TypeError, ValueError):
        return 100.0, 5.0, 2.5, 5.0, 10.0, {}


(
    _MAX_RISK_SCORE,
    _T_ENTER,
    _T_EXIT,
    _SEVERITY_MEDIUM_MIN,
    _SEVERITY_HIGH_MIN,
    _SIGNAL_WEIGHTS,
) = _load_fusion_limits()
_STATE_VALUES = {"NORMAL": 0, "SUSPICIOUS": 1, "ALERT": 2}
_VIOLATION_BY_SIGNAL = {
    "FACE_PRESENCE": "FACE_ABSENT",
    "MULTI_FACE": "MULTIPLE_FACES",
    "EYE_STATE": "EYES_CLOSED",
    "MOUTH_STATE": "TALKING",
    "OBJECT_PRESENCE": "OBJECT_DETECTED",
    "HEAD_POSE": "HEAD_POSE_AWAY",
    "IDENTITY": "IDENTITY_MISMATCH",
}

_BROWSER_EVENT_BASE_SEVERITY = {
    "MEDIA_READY": "LOW",
    "CONTENT_MONITOR_READY": "LOW",
    "TAB_HIDDEN": "LOW",
    "TAB_VISIBLE": "LOW",
    "WINDOW_BLUR": "LOW",
    "WINDOW_FOCUS": "LOW",
    "TAB_SWITCHED": "MEDIUM",
    "NEW_TAB": "MEDIUM",
    "NAVIGATION_AWAY": "HIGH",
    "FULLSCREEN_EXIT": "HIGH",
    "FULLSCREEN_ENTER": "LOW",
    "CLIPBOARD_COPY": "MEDIUM",
    "CLIPBOARD_PASTE": "MEDIUM",
    "CONTEXT_MENU": "MEDIUM",
    "CAMERA_MUTED": "HIGH",
    "CAMERA_ENDED": "HIGH",
    "MICROPHONE_MUTED": "HIGH",
    "MICROPHONE_ENDED": "HIGH",
    "SCREEN_SHARE_ENDED": "HIGH",
    "MONITOR_CLOSED": "HIGH",
    "PERMISSION_MISSING": "HIGH",
}


def _browser_event_severity(event_type: str, exam: models.Exam) -> str:
    severity = _BROWSER_EVENT_BASE_SEVERITY[event_type]
    if event_type == "FULLSCREEN_EXIT" and not exam.require_fullscreen:
        return "LOW"
    if event_type.startswith("CLIPBOARD_") or event_type == "CONTEXT_MENU":
        return severity if exam.block_clipboard else "LOW"
    if event_type.startswith("CAMERA_") and not exam.require_camera:
        return "LOW"
    if event_type.startswith("MICROPHONE_") and not exam.require_microphone:
        return "LOW"
    if event_type == "SCREEN_SHARE_ENDED" and not exam.require_screen_share:
        return "LOW"
    return severity


def _integrity_score_after(current: float, severity: str) -> float:
    increment = {"LOW": 0.0, "MEDIUM": 5.0, "HIGH": 20.0}[severity]
    return min(100.0, current + increment)


def _integrity_status(score: float) -> str:
    if score >= 20.0:
        return "alert"
    if score >= 5.0:
        return "warning"
    return "healthy"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat(timespec="milliseconds")


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _risk_state_is_possible(risk_score: float, session_state: str, previous_state: str) -> bool:
    if risk_score > _MAX_RISK_SCORE + 1e-6:
        return False
    expected_state = previous_state
    if previous_state == "SESSION_NORMAL" and risk_score >= _T_ENTER:
        expected_state = "SESSION_ALERT"
    elif previous_state == "SESSION_ALERT" and risk_score <= _T_EXIT:
        expected_state = "SESSION_NORMAL"
    return session_state == expected_state


def _risk_from_signal_states(signal_states: dict[str, str]) -> float:
    return sum(
        _SIGNAL_WEIGHTS.get(name, 0.0) * _STATE_VALUES[state]
        for name, state in signal_states.items()
    )


def _primary_violation_from_states(signal_states: dict[str, str]) -> Optional[str]:
    active = [name for name in _SIGNAL_WEIGHTS if signal_states.get(name) != "NORMAL"]
    if not active:
        return None
    primary_signal = max(
        active,
        key=lambda name: _SIGNAL_WEIGHTS[name] * _STATE_VALUES[signal_states[name]],
    )
    return _VIOLATION_BY_SIGNAL[primary_signal]


def _severity_for(risk_score: float) -> str:
    if risk_score >= _SEVERITY_HIGH_MIN:
        return "HIGH"
    if risk_score >= _SEVERITY_MEDIUM_MIN:
        return "MEDIUM"
    return "LOW"


async def _send_validation_error(websocket: WebSocket, code: str) -> None:
    try:
        await websocket.send_json({"type": "error", "code": code})
    except Exception:
        pass


@router.websocket("/ws/client")
async def client_ws(websocket: WebSocket) -> None:
    try:
        session_id = decode_session_websocket(websocket)
    except Exception:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    exam_session: Optional[models.ExamSession] = None
    exam_id: Optional[str] = None
    ended_normally = False
    client_registered = False
    disconnect_reason = "client_disconnected"
    try:
        exam_session = db.get(models.ExamSession, session_id)
        if exam_session is None:
            await websocket.close(code=4404)
            return
        if exam_session.status == "ended":
            await websocket.close(code=4409)
            return

        exam_id = exam_session.exam_id
        exam_session.status = "active"
        exam_session.last_seen_at = _now()
        exam_session.disconnect_reason = None
        db.commit()
        if not await manager.connect_client(session_id, websocket):
            await websocket.close(code=4409)
            return
        client_registered = True

        invalid_messages = 0
        last_video_time = -1.0
        last_telemetry_client_video_time: Optional[float] = None
        seen_event_ids: set[str] = set()
        last_signal_states: Optional[dict[str, str]] = None
        last_signal_values: Optional[dict[str, float]] = None
        pending_violation_transition = False
        recent_message_times: deque[float] = deque()
        hello_received = exam_session.client_type != "browser_extension"
        last_browser_sequence = -1
        focus_lost_server_at: Optional[datetime] = None

        while True:
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(), timeout=_CLIENT_IDLE_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                disconnect_reason = "heartbeat_timeout"
                await websocket.close(code=4408)
                break
            await manager.touch_client(session_id)

            monotonic_now = time.monotonic()
            recent_message_times.append(monotonic_now)
            while recent_message_times and monotonic_now - recent_message_times[0] > 1.0:
                recent_message_times.popleft()
            if len(recent_message_times) > _MAX_MESSAGES_PER_SECOND:
                disconnect_reason = "message_rate_exceeded"
                await websocket.close(code=4429)
                break
            if len(raw) > _MAX_MESSAGE_CHARS:
                disconnect_reason = "message_too_large"
                await websocket.close(code=4409)
                break

            try:
                message = json.loads(raw)
                if not isinstance(message, dict) or set(message) != {"type", "data"}:
                    raise ValueError("Sai envelope")
                msg_type = message["type"]
                model_type = MESSAGE_DATA_MODELS.get(msg_type)
                if model_type is None:
                    raise ValueError("Loai message khong duoc ho tro")
                data = model_type.model_validate(message["data"])
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
                invalid_messages += 1
                await _send_validation_error(websocket, "invalid_message")
                if invalid_messages >= _MAX_INVALID_MESSAGES:
                    disconnect_reason = "too_many_invalid_messages"
                    await websocket.close(code=4400)
                    break
                continue

            invalid_messages = 0
            received_at = _now()
            received_iso = received_at.isoformat(timespec="milliseconds")
            exam_session.last_seen_at = received_at

            if msg_type == "heartbeat":
                db.commit()
                continue

            if msg_type == "client_hello":
                assert isinstance(data, ClientHelloData)
                if (
                    exam_session.client_type != "browser_extension"
                    or hello_received
                    or data.extension_version != exam_session.extension_version
                    or data.browser_name.casefold() != (exam_session.browser_name or "").casefold()
                    or hash_device_id(str(data.device_id)) != exam_session.device_id_hash
                ):
                    disconnect_reason = "client_identity_mismatch"
                    await _send_validation_error(websocket, "client_identity_mismatch")
                    await websocket.close(code=4403)
                    break
                hello_received = True
                exam_session.browser_version = data.browser_version
                exam_session.platform = data.platform
                exam_session.capabilities_json = json.dumps(sorted(data.capabilities))
                await websocket.send_json(
                    {
                        "type": "hello_ack",
                        "data": {
                            "session_id": session_id,
                            "server_time": received_iso,
                            "client_idle_timeout_sec": _CLIENT_IDLE_TIMEOUT_SEC,
                        },
                    }
                )
                db.commit()
                continue

            if msg_type == "browser_event":
                assert isinstance(data, BrowserEventData)
                if exam_session.client_type != "browser_extension" or not hello_received:
                    await _send_validation_error(websocket, "client_hello_required")
                    continue
                if data.sequence <= last_browser_sequence:
                    await _send_validation_error(websocket, "invalid_event_sequence")
                    continue
                if browser_event_exists(session_id, data.event_id):
                    last_browser_sequence = data.sequence
                    await websocket.send_json(
                        {
                            "type": "browser_event_ack",
                            "data": {"event_id": data.event_id, "duplicate": True},
                        }
                    )
                    continue

                last_browser_sequence = data.sequence
                exam = exam_session.exam
                severity = _browser_event_severity(data.event_type, exam)
                server_duration_ms: Optional[int] = None
                if data.event_type in {"WINDOW_BLUR", "TAB_HIDDEN", "TAB_SWITCHED"}:
                    focus_lost_server_at = received_at
                elif data.event_type in {"WINDOW_FOCUS", "TAB_VISIBLE"} and focus_lost_server_at:
                    server_duration_ms = max(
                        0, int((received_at - focus_lost_server_at).total_seconds() * 1000),
                    )
                    if server_duration_ms > int(exam.max_focus_loss_seconds * 1000):
                        severity = "HIGH"
                    focus_lost_server_at = None

                snapshot_path = None
                if data.snapshot is not None:
                    try:
                        snapshot_path = save_uploaded_snapshot(
                            session_id,
                            data.event_id,
                            data.snapshot.content_type,
                            data.snapshot.data_base64,
                            data.snapshot.sha256,
                        )
                    except ValueError:
                        await _send_validation_error(websocket, "invalid_snapshot")
                        continue

                elapsed_server = max(
                    0.0, (received_at - _as_utc(exam_session.started_at)).total_seconds(),
                )
                record = data.model_dump(mode="json", exclude={"snapshot"})
                record["client_timestamp"] = str(record["client_timestamp"])
                record["timestamp"] = received_iso
                record["video_time_sec"] = round(elapsed_server, 3)
                record["severity"] = severity
                record["server_duration_ms"] = server_duration_ms
                record["snapshot_path"] = snapshot_path
                record["server_received_at"] = received_iso
                append_jsonl(session_id, "browser_events.jsonl", record)

                exam_session.browser_event_count += 1
                if data.event_type == "MEDIA_READY":
                    exam_session.camera_status = (
                        "ready" if exam.require_camera else "not_required"
                    )
                    exam_session.microphone_status = (
                        "ready" if exam.require_microphone else "not_required"
                    )
                    exam_session.screen_share_status = (
                        "ready" if exam.require_screen_share else "not_required"
                    )
                elif data.event_type.startswith("CAMERA_"):
                    exam_session.camera_status = "issue"
                elif data.event_type.startswith("MICROPHONE_"):
                    exam_session.microphone_status = "issue"
                elif data.event_type == "SCREEN_SHARE_ENDED":
                    exam_session.screen_share_status = "issue"
                elif data.event_type == "PERMISSION_MISSING":
                    missing_component = str(data.metadata.get("component", ""))
                    if missing_component == "camera":
                        exam_session.camera_status = "issue"
                    elif missing_component == "microphone":
                        exam_session.microphone_status = "issue"
                    elif missing_component == "screen_share":
                        exam_session.screen_share_status = "issue"
                exam_session.integrity_score_current = _integrity_score_after(
                    exam_session.integrity_score_current, severity,
                )
                exam_session.integrity_status_current = _integrity_status(
                    exam_session.integrity_score_current,
                )
                db.commit()
                await manager.broadcast_to_dashboard(
                    exam_id,
                    {
                        "type": "browser_event",
                        "session_id": session_id,
                        "student_name": exam_session.student_name,
                        "data": {
                            **record,
                            "integrity_score": exam_session.integrity_score_current,
                            "integrity_status": exam_session.integrity_status_current,
                            "browser_event_count": exam_session.browser_event_count,
                            "camera_status": exam_session.camera_status,
                            "microphone_status": exam_session.microphone_status,
                            "screen_share_status": exam_session.screen_share_status,
                        },
                        "server_received_at": received_iso,
                    },
                )
                await websocket.send_json(
                    {
                        "type": "browser_event_ack",
                        "data": {"event_id": data.event_id, "duplicate": False},
                    }
                )
                continue

            if msg_type == "end_session":
                exam_session.status = "ended"
                exam_session.ended_at = received_at
                exam_session.disconnect_reason = None if data.reason == "completed" else data.reason
                db.commit()
                meta = build_session_meta(
                    session_id, exam_session.started_at, exam_session.ended_at,
                    end_reason=data.reason,
                    student_name=exam_session.student_name,
                    candidate_number=exam_session.candidate_number,
                    candidate_email=exam_session.candidate_email,
                    authentication_method=exam_session.authentication_method,
                    client_type=exam_session.client_type,
                    extension_version=exam_session.extension_version,
                )
                write_session_meta(session_id, meta)
                await manager.broadcast_to_dashboard(
                    exam_id,
                    {
                        "type": "session_ended",
                        "session_id": session_id,
                        "student_name": exam_session.student_name,
                        "data": {"reason": data.reason},
                        "server_received_at": received_iso,
                    },
                )
                ended_normally = True
                await websocket.close(code=1000)
                break

            server_video_time_sec: Optional[float] = None
            if hasattr(data, "video_time_sec"):
                elapsed_server = max(0.0, (received_at - _as_utc(exam_session.started_at)).total_seconds())
                if data.video_time_sec > elapsed_server + 60.0 or data.video_time_sec + 2.0 < last_video_time:
                    await _send_validation_error(websocket, "invalid_timeline")
                    continue
                last_video_time = max(last_video_time, data.video_time_sec)
                server_video_time_sec = round(elapsed_server, 3)

            if msg_type == "telemetry_update":
                computed_risk = _risk_from_signal_states(data.signal_states)
                previous_session_state = exam_session.session_state_current
                if (
                    abs(computed_risk - data.risk_score) > 1e-3
                    or not _risk_state_is_possible(
                        data.risk_score,
                        data.session_state,
                        exam_session.session_state_current,
                    )
                ):
                    await _send_validation_error(websocket, "invalid_risk_state")
                    continue
                previous_signal_states = last_signal_states or {
                    name: "NORMAL" for name in _SIGNAL_WEIGHTS
                }
                risk_record = data.model_dump(mode="json", exclude={"signals", "signal_states"})
                risk_record["client_timestamp"] = risk_record.pop("timestamp")
                risk_record["client_video_time_sec"] = risk_record["video_time_sec"]
                risk_record["video_time_sec"] = server_video_time_sec
                risk_record["timestamp"] = received_at.timestamp()
                risk_record["server_received_at"] = received_iso
                append_jsonl(session_id, "risk_score_timeline.jsonl", risk_record)
                if isinstance(data, TelemetryUpdateData):
                    for signal in data.signals:
                        signal_record = signal.model_dump(mode="json")
                        signal_record["client_timestamp"] = signal_record.pop("timestamp")
                        signal_record["timestamp"] = received_at.timestamp()
                        signal_record["video_time_sec"] = data.video_time_sec
                        signal_record["server_received_at"] = received_iso
                        append_jsonl(session_id, "signals.jsonl", signal_record)

                for name, new_state in data.signal_states.items():
                    old_state = previous_signal_states[name]
                    if old_state != new_state:
                        append_jsonl(
                            session_id,
                            "state_transitions.jsonl",
                            {
                                "timestamp": received_at.timestamp(),
                                "scope": "signal",
                                "signal_name": name,
                                "from_state": old_state,
                                "to_state": new_state,
                                "server_received_at": received_iso,
                            },
                        )
                if previous_session_state != data.session_state:
                    append_jsonl(
                        session_id,
                        "state_transitions.jsonl",
                        {
                            "timestamp": received_at.timestamp(),
                            "scope": "session",
                            "from_state": previous_session_state,
                            "to_state": data.session_state,
                            "risk_score": data.risk_score,
                            "server_received_at": received_iso,
                        },
                    )
                if previous_session_state == "SESSION_NORMAL" and data.session_state == "SESSION_ALERT":
                    pending_violation_transition = True
                elif data.session_state == "SESSION_NORMAL":
                    pending_violation_transition = False

                exam_session.risk_score_current = data.risk_score
                exam_session.session_state_current = data.session_state
                last_signal_states = dict(data.signal_states)
                last_signal_values = {signal.signal_name: signal.value for signal in data.signals}
                last_telemetry_client_video_time = data.video_time_sec
                db.commit()
                await manager.broadcast_to_dashboard(
                    exam_id,
                    {
                        "type": "risk_update",
                        "session_id": session_id,
                        "student_name": exam_session.student_name,
                        "data": risk_record,
                        "server_received_at": received_iso,
                    },
                )
                continue

            if msg_type == "violation_event":
                assert isinstance(data, ViolationEventData)
                if data.event_id in seen_event_ids or violation_event_exists(session_id, data.event_id):
                    await _send_validation_error(websocket, "duplicate_event")
                    continue
                if (
                    last_signal_states is None
                    or last_signal_values is None
                    or not pending_violation_transition
                    or data.session_id != session_id
                    or last_telemetry_client_video_time is None
                    or abs(data.video_time_sec - last_telemetry_client_video_time) > 2.0
                    or exam_session.session_state_current != "SESSION_ALERT"
                    or abs(data.risk_score - exam_session.risk_score_current) > 1e-3
                    or data.severity != _severity_for(data.risk_score)
                ):
                    await _send_validation_error(websocket, "inconsistent_violation")
                    continue
                active_names = {
                    name for name, state in last_signal_states.items() if state != "NORMAL"
                }
                contributions_by_name = {
                    item.signal_name: item for item in data.contributing_signals
                }
                contributions_are_consistent = (
                    set(contributions_by_name) == active_names
                    and all(
                        item.state == last_signal_states[name]
                        and abs(item.value - last_signal_values[name]) <= 1e-6
                        and abs(item.weight - _SIGNAL_WEIGHTS[name]) <= 1e-6
                        and item.violation_type == _VIOLATION_BY_SIGNAL[name]
                        for name, item in contributions_by_name.items()
                    )
                )
                expected_primary = _primary_violation_from_states(last_signal_states)
                if not contributions_are_consistent or data.primary_violation != expected_primary:
                    await _send_validation_error(websocket, "invalid_primary_violation")
                    continue

                snapshot_path = None
                if data.snapshot is not None:
                    try:
                        snapshot_path = save_uploaded_snapshot(
                            session_id,
                            data.event_id,
                            data.snapshot.content_type,
                            data.snapshot.data_base64,
                            data.snapshot.sha256,
                        )
                    except ValueError:
                        await _send_validation_error(websocket, "invalid_snapshot")
                        continue

                record = data.model_dump(mode="json", exclude={"snapshot"})
                record["session_id"] = session_id
                record["client_timestamp"] = record.pop("timestamp")
                record["client_video_time_sec"] = record["video_time_sec"]
                record["video_time_sec"] = server_video_time_sec
                record["timestamp"] = received_iso
                record["snapshot_path"] = snapshot_path
                record["server_received_at"] = received_iso
                append_jsonl(session_id, "violations.jsonl", record)
                seen_event_ids.add(data.event_id)
                pending_violation_transition = False
                db.commit()
                await manager.broadcast_to_dashboard(
                    exam_id,
                    {
                        "type": "violation_event",
                        "session_id": session_id,
                        "student_name": exam_session.student_name,
                        "data": record,
                        "server_received_at": received_iso,
                    },
                )
                continue

    except WebSocketDisconnect:
        disconnect_reason = "client_disconnected"
    finally:
        if client_registered:
            await manager.disconnect_client(session_id, websocket)
        if client_registered and exam_session is not None and exam_id is not None and not ended_normally:
            try:
                db.refresh(exam_session)
                if exam_session.status != "ended":
                    exam_session.status = "disconnected"
                    exam_session.last_seen_at = _now()
                    exam_session.disconnect_reason = disconnect_reason
                    db.commit()
                    await manager.broadcast_to_dashboard(
                        exam_id,
                        {
                            "type": "session_disconnected",
                            "session_id": session_id,
                            "student_name": exam_session.student_name,
                            "data": {"reason": disconnect_reason},
                            "server_received_at": _now_iso(),
                        },
                    )
            except Exception:
                db.rollback()
        db.close()


@router.websocket("/ws/dashboard/{exam_id}")
async def dashboard_ws(websocket: WebSocket, exam_id: str) -> None:
    db = SessionLocal()
    user_id: Optional[str] = None
    session_version: Optional[int] = None
    try:
        try:
            user = decode_user_websocket(websocket, db)
        except Exception:
            await websocket.close(code=4401)
            return
        try:
            authorize_exam(db, user, exam_id, Permission.EXAM_MONITOR)
        except Exception:
            await websocket.close(code=4404)
            return
        user_id = user.id
        session_version = user.session_version
    finally:
        db.close()

    await manager.connect_dashboard(exam_id, websocket)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                pass
            validation_db = SessionLocal()
            try:
                current_user = validation_db.get(models.User, user_id)
                if (
                    current_user is None
                    or current_user.status != "active"
                    or current_user.session_version != session_version
                ):
                    await websocket.close(code=4403)
                    return
                authorize_exam(
                    validation_db,
                    current_user,
                    exam_id,
                    Permission.EXAM_MONITOR,
                )
            except Exception:
                await websocket.close(code=4403)
                return
            finally:
                validation_db.close()
            await websocket.send_json({"type": "server_heartbeat", "server_received_at": _now_iso()})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_dashboard(exam_id, websocket)
