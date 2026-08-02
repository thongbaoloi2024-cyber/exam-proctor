"""AppController - gop IDLE (nhap ten+join-code) -> ENROLLMENT -> MONITORING
-> GENERATING_REPORT -> ENDED thanh 1 vong lap per-frame duy nhat, thay 2
vong lap `while` tach biet cu trong main.py (truoc Tuan 13) - dung huong da
chot o docs/KE_HOACH_CHI_TIET_TUAN12.md muc 1.3.

`step(raw_frame) -> np.ndarray` la ham DUY NHAT `main.py` can goi moi frame;
`handle_mouse`/`handle_key` xu ly tuong tac chuot/ban phim truoc frame tiep
theo.

Tich hop backend (Tuan 12 moi, xem docs/KE_HOACH_PLATFORM.md): neu
`config.backend.enabled=True`, IDLE yeu cau nhap ten + join-code, goi
`join_exam()` (REST) de lay session_token, roi mo `BackendClient` (WebSocket)
gui telemetry theo lo va `ViolationEvent` trong luc MONITORING - hoan toan
"best-effort": neu backend khong ket noi duoc, phien van chay binh thuong
CHI cuc bo (ghi JSONL local, sinh bao cao local) dung tinh than offline-first.
"""
from __future__ import annotations

import dataclasses
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np

from src.app_config import AppConfig
from src.client.backend_client import BackendClient, join_exam
from src.fusion.engine import RiskFusionEngine
from src.fusion.risk_score_logger import RiskScoreLogger
from src.fusion.state_transition_logger import StateTransitionLogger
from src.orchestrator import PipelineOrchestrator
from src.reporting.report_generator import generate_report
from src.signals.liveness import BlinkLivenessChallenge
from src.ui.app_state import AppState
from src.ui.button import Button
from src.ui.overlay import (
    draw_ended_screen,
    draw_enrollment_progress,
    draw_generating_report_message,
    draw_idle_screen,
    draw_monitoring_overlay,
)
from src.ui.text_field import TextField

DEFAULT_FUSION_CONFIG_PATH = os.path.join("config", "fusion.yaml")


def _iso(ts: float) -> str:
    # fromtimestamp(..., tz=utc).astimezone() thay vi fromtimestamp(ts) tran
    # (naive) roi .astimezone() - tranh OSError tren Windows voi epoch nho
    # (cung 1 ly do da ghi o src/fusion/engine.py).
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _append_jsonl(path: str, record: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_session_meta_local(
    path: str, session_id: str, started_at: float, ended_at: float, frame_count: int,
) -> None:
    duration_sec = ended_at - started_at
    meta = {
        "session_id": session_id,
        "started_at": _iso(started_at),
        "ended_at": _iso(ended_at),
        "duration_sec": round(duration_sec, 1),
        "fusion_config_version": "v1",
        "fps_avg": round(frame_count / duration_sec, 2) if duration_sec > 0 else 0.0,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


class AppController:
    def __init__(
        self,
        config: AppConfig,
        signals: Dict[str, Any],
        perception: Any,
        report_fn: Callable[..., Dict[str, Path]] = generate_report,
        fusion_config_path: str = DEFAULT_FUSION_CONFIG_PATH,
    ) -> None:
        """`signals` phai co dung key "IDENTITY" (dung cho enrollment) - xem
        `src/signals/factory.py`. `perception` truyen vao tuong minh (khong
        tu tao `PerceptionLayer()` mac dinh o day) de test dung duoc fake
        nhe, khong phai khoi tao MTCNN/FaceMesh/YOLO that."""
        self._config = config
        self._signals = signals
        self._perception = perception
        self._report_fn = report_fn
        self._fusion_config_path = fusion_config_path

        self.state = AppState.IDLE

        self._name_field = TextField(rect=(20, 100, 300, 30), label="Ten", active=True)
        self._code_field = TextField(rect=(20, 140, 300, 30), label="Ma tham gia", uppercase=True)
        self._start_button = Button(rect=(20, 180, 120, 40), label="Bat dau")
        self._end_button = Button(rect=(500, 400, 120, 40), label="Ket thuc")
        self._idle_error: Optional[str] = None

        self._backend_client: Optional[BackendClient] = None
        self._last_telemetry_sent_at: Optional[float] = None

        self._session_id: Optional[str] = None
        self._session_dir: Optional[str] = None
        self._violations_log_path: Optional[str] = None
        self._session_meta_path: Optional[str] = None
        self._orchestrator: Optional[PipelineOrchestrator] = None
        self._fusion_engine: Optional[RiskFusionEngine] = None
        self._state_logger: Optional[StateTransitionLogger] = None
        self._risk_score_logger: Optional[RiskScoreLogger] = None
        self._started_at: Optional[float] = None

        self._enrollment_frames: List[np.ndarray] = []
        self._enrollment_attempt = 1
        self._enrollment_started_at: Optional[float] = None
        self._identity_enrolled = False
        self._liveness_challenge: Optional[BlinkLivenessChallenge] = None

        self._report_paths: Dict[str, Path] = {}
        self._summary_sentence = ""

    # ------------------------------------------------------------------
    # Tuong tac chuot/ban phim
    # ------------------------------------------------------------------

    def handle_mouse(self, event: int, x: int, y: int) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return

        if self.state == AppState.IDLE:
            if self._name_field.contains(x, y):
                self._name_field.active = True
                self._code_field.active = False
            elif self._code_field.contains(x, y):
                self._name_field.active = False
                self._code_field.active = True
            elif self._start_button.contains(x, y):
                self._try_start()
        elif self.state == AppState.MONITORING:
            if self._end_button.contains(x, y):
                self.state = AppState.GENERATING_REPORT

    def handle_key(self, key: int) -> None:
        if key in (-1, 255):
            return
        if self.state == AppState.IDLE:
            if key == 9:  # Tab - chuyen focus giua 2 o nhap
                self._name_field.active, self._code_field.active = (
                    self._code_field.active, self._name_field.active,
                )
                return
            self._name_field.handle_key(key)
            self._code_field.handle_key(key)
        elif self.state == AppState.MONITORING:
            if key in (ord("q"), 27):
                self.state = AppState.GENERATING_REPORT

    def shutdown(self) -> None:
        """Close logs/network resources when the camera loop exits unexpectedly."""
        if self.state in {AppState.MONITORING, AppState.GENERATING_REPORT}:
            self._finalize_session()
            self.state = AppState.ENDED
        elif self.state == AppState.ENROLLMENT:
            self._abort_session("client_shutdown")
            self.state = AppState.IDLE

    # ------------------------------------------------------------------
    # step() - 1 frame
    # ------------------------------------------------------------------

    def step(self, raw_frame: np.ndarray) -> np.ndarray:
        if self.state == AppState.IDLE:
            return self._step_idle(raw_frame)
        if self.state == AppState.ENROLLMENT:
            return self._step_enrollment(raw_frame)
        if self.state == AppState.MONITORING:
            return self._step_monitoring(raw_frame)
        if self.state == AppState.GENERATING_REPORT:
            return self._step_generating_report(raw_frame)
        return self._step_ended(raw_frame)

    def _step_idle(self, raw_frame: np.ndarray) -> np.ndarray:
        display = raw_frame.copy()
        draw_idle_screen(display, self._name_field, self._code_field, self._start_button, self._idle_error)
        return display

    def _step_enrollment(self, raw_frame: np.ndarray) -> np.ndarray:
        preprocessed, perception_result = self._perception.process(raw_frame)
        if self._liveness_challenge is not None:
            self._liveness_challenge.update(perception_result)

        liveness_ok = self._liveness_challenge is None or self._liveness_challenge.verified
        # Bind enrollment to the liveness challenge: reference embeddings are
        # captured only after the observed open->closed->open sequence, not
        # from frames shown before the challenge completed.
        if not self._identity_enrolled and liveness_ok:
            self._enrollment_frames.append(preprocessed.rgb)

        display = preprocessed.resized_bgr.copy()
        liveness_prompt = self._liveness_challenge.prompt if self._liveness_challenge is not None else None
        draw_enrollment_progress(
            display,
            min(len(self._enrollment_frames), self._config.enrollment.num_frames),
            self._config.enrollment.num_frames,
            liveness_prompt=liveness_prompt,
        )

        if (
            not self._identity_enrolled
            and liveness_ok
            and len(self._enrollment_frames) >= self._config.enrollment.num_frames
        ):
            identity_signal = self._signals["IDENTITY"]
            success = identity_signal.enroll(self._enrollment_frames)
            self._enrollment_frames = []
            if success:
                self._identity_enrolled = True
            else:
                self._enrollment_attempt += 1
                if self._enrollment_attempt > self._config.enrollment.max_attempts:
                    # Het luot thu - quay ve IDLE thay vi treo (giu dung
                    # edge case da co o _run_enrollment cu, main.py Tuan 6).
                    self._abort_session("enrollment_failed")
                    self.state = AppState.IDLE
                    self._idle_error = "Khong tim thay khuon mat sau nhieu lan thu - vui long thu lai."

        if self._identity_enrolled and liveness_ok:
            self.state = AppState.MONITORING
        elif (
            self._liveness_challenge is not None
            and not liveness_ok
            and self._enrollment_started_at is not None
            and time.time() - self._enrollment_started_at > self._config.enrollment.liveness_timeout_sec
        ):
            self._abort_session("enrollment_failed")
            self.state = AppState.IDLE
            self._idle_error = "Kiem tra song khong thanh cong - vui long thu lai va chop mat theo huong dan."

        return display

    def _step_monitoring(self, raw_frame: np.ndarray) -> np.ndarray:
        preprocessed, perception_result, results = self._orchestrator.process_frame(raw_frame)

        violation_event = self._fusion_engine.update(results, frame_bgr=preprocessed.resized_bgr)
        now = time.time()
        should_send_telemetry = (
            self._backend_client is not None
            and (
                violation_event is not None
                or self._last_telemetry_sent_at is None
                or now - self._last_telemetry_sent_at >= self._config.backend.telemetry_interval_sec
            )
        )
        if should_send_telemetry:
            self._backend_client.send_telemetry_update(
                results=results,
                signal_states={
                    name: state.value for name, state in self._fusion_engine.tracker.states().items()
                },
                risk_score=self._fusion_engine.last_risk_score,
                session_state=self._fusion_engine.session_state.value,
                video_time_sec=now - self._started_at,
                timestamp=now,
            )
            self._last_telemetry_sent_at = now

        if violation_event is not None:
            _append_jsonl(self._violations_log_path, dataclasses.asdict(violation_event))
            if self._backend_client is not None:
                self._backend_client.send_violation_event(violation_event)

        display = preprocessed.resized_bgr.copy()
        states = self._fusion_engine.tracker.states()
        draw_monitoring_overlay(
            display, perception_result, results, states, self._fusion_engine.session_state.value, self._end_button,
        )
        return display

    def _step_generating_report(self, raw_frame: np.ndarray) -> np.ndarray:
        display = raw_frame.copy()
        draw_generating_report_message(display)
        self._finalize_session()
        self.state = AppState.ENDED
        return display

    def _step_ended(self, raw_frame: np.ndarray) -> np.ndarray:
        display = raw_frame.copy()
        report_path = self._report_paths.get("pdf") or self._report_paths.get("html")
        draw_ended_screen(display, self._summary_sentence, str(report_path) if report_path else None)
        return display

    # ------------------------------------------------------------------
    # Chi tiet tung buoc chuyen trang thai
    # ------------------------------------------------------------------

    def _try_start(self) -> None:
        if self._config.backend.enabled:
            student_name = self._name_field.value.strip()
            join_code = self._code_field.value.strip()
            if not student_name or not join_code:
                self._idle_error = "Vui long nhap ten va ma tham gia."
                return

            join_result = join_exam(self._config.backend.base_url, join_code, student_name)
            if join_result is None:
                self._idle_error = "Ma tham gia khong hop le hoac khong ket noi duoc backend."
                return

            self._session_id = join_result.session_id
            self._backend_client = BackendClient(self._config.backend.ws_url, join_result.session_token)
            self._backend_client.connect()  # best-effort, offline-first neu that bai
        else:
            self._session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")

        self._idle_error = None
        self._enrollment_attempt = 1
        self._start_session()
        self.state = AppState.ENROLLMENT

    def _start_session(self) -> None:
        session_dir = os.path.join(self._config.sessions_dir, self._session_id)
        snapshot_dir = os.path.join(session_dir, "snapshots")
        os.makedirs(session_dir, exist_ok=True)

        self._session_dir = session_dir
        signal_log_path = os.path.join(session_dir, "signals.jsonl")
        state_log_path = os.path.join(session_dir, "state_transitions.jsonl")
        self._violations_log_path = os.path.join(session_dir, "violations.jsonl")
        risk_score_log_path = os.path.join(session_dir, "risk_score_timeline.jsonl")
        self._session_meta_path = os.path.join(session_dir, "session_meta.json")

        self._state_logger = StateTransitionLogger(state_log_path)
        self._risk_score_logger = RiskScoreLogger(risk_score_log_path)
        self._fusion_engine = RiskFusionEngine.from_config(
            self._fusion_config_path, session_id=self._session_id, snapshot_dir=snapshot_dir,
            logger=self._state_logger, risk_score_logger=self._risk_score_logger,
        )
        self._orchestrator = PipelineOrchestrator(
            self._perception, list(self._signals.values()), log_path=signal_log_path,
        )
        self._started_at = time.time()
        self._enrollment_frames = []
        self._enrollment_started_at = self._started_at
        self._identity_enrolled = False
        self._last_telemetry_sent_at = None
        if self._config.enrollment.require_liveness:
            eye_cfg = self._signals.get("EYE_STATE")
            ear_threshold = getattr(eye_cfg, "_ear_threshold", 0.21)
            self._liveness_challenge = BlinkLivenessChallenge(
                ear_threshold=ear_threshold,
                min_open_frames=self._config.enrollment.liveness_min_open_frames,
                min_closed_frames=self._config.enrollment.liveness_min_closed_frames,
            )
        else:
            self._liveness_challenge = None

    def _close_session_resources(self) -> None:
        if self._orchestrator is not None:
            self._orchestrator.close()
        if self._state_logger is not None:
            self._state_logger.close()
        if self._risk_score_logger is not None:
            self._risk_score_logger.close()

    def _abort_session(self, reason: str) -> None:
        ended_at = time.time()
        if self._session_meta_path and self._session_id and self._started_at is not None:
            frame_count = self._orchestrator.frame_count if self._orchestrator is not None else 0
            _write_session_meta_local(
                self._session_meta_path, self._session_id, self._started_at, ended_at, frame_count,
            )
        self._close_session_resources()
        if self._backend_client is not None:
            self._backend_client.send_end_session(reason=reason)
            self._backend_client.close()
        self._backend_client = None
        self._orchestrator = None
        self._state_logger = None
        self._risk_score_logger = None

    def _finalize_session(self) -> None:
        ended_at = time.time()
        frame_count = self._orchestrator.frame_count if self._orchestrator is not None else 0
        _write_session_meta_local(self._session_meta_path, self._session_id, self._started_at, ended_at, frame_count)

        self._close_session_resources()

        if self._backend_client is not None:
            self._backend_client.send_end_session()
            self._backend_client.close()

        if self._config.report.auto_generate:
            self._report_paths = self._report_fn(
                self._session_dir,
                fusion_config_path=self._fusion_config_path,
                formats=self._config.report.formats,
            )
            preferred_format = next(
                (fmt for fmt in self._config.report.formats if fmt in self._report_paths), None,
            )
            if self._config.report.auto_open and preferred_format is not None:
                try:
                    os.startfile(self._report_paths[preferred_format])  # type: ignore[attr-defined]
                except (AttributeError, OSError):
                    pass  # khong phai Windows, hoac khong mo duoc - khong crash app
        else:
            self._report_paths = {}

        self._summary_sentence = f"Phien {self._session_id} da ket thuc sau {ended_at - self._started_at:.1f} giay."
