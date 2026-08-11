"""Sinh dữ liệu tổng hợp quy mô lớn cho dashboard và báo cáo DATT.

Script tạo đồng bộ dữ liệu quan hệ (organization users, memberships, exams,
assignments, sessions, incident reviews) và evidence files trong
``sessions/<session_id>``.  Dữ liệu được cô lập bằng ``batch_id`` và dùng UUID
xác định để tránh va chạm với dữ liệu thật.

Ví dụ:
    python scripts/generate_report_dataset.py --dry-run
    python scripts/generate_report_dataset.py --target-email test@gmail.com
    python scripts/generate_report_dataset.py --session-count 100 --sample-reports 2

Nếu ``REPORT_DATA_PASSWORD`` không được đặt, script sinh một mật khẩu mạnh
ngẫu nhiên và ghi thông tin đăng nhập vào ``generated_reports/<batch>/accounts.csv``.
Chỉ dùng các tài khoản này cho môi trường demo/phát triển.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import io
import json
import os
import random
import re
import secrets
import shutil
import sys
import uuid
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from backend import models  # noqa: E402
from backend.auth import hash_password  # noqa: E402
from backend.db import Base, DATABASE_URL, SessionLocal, engine  # noqa: E402
from backend.db_migrations import apply_additive_migrations  # noqa: E402
from src.fusion.config import load_session_thresholds  # noqa: E402
from src.fusion.engine import RiskFusionEngine  # noqa: E402
from src.fusion.risk_score_logger import RiskScoreLogger  # noqa: E402
from src.fusion.state_transition_logger import StateTransitionLogger  # noqa: E402
from src.reporting.report_generator import generate_report  # noqa: E402
from src.signals.base import SignalResult  # noqa: E402


UTC = timezone.utc
NAMESPACE = uuid.UUID("90256b54-b586-4bd0-bb99-fca0eeb74adc")

SIGNAL_NAMES = (
    "FACE_PRESENCE", "MULTI_FACE", "EYE_STATE", "MOUTH_STATE",
    "OBJECT_PRESENCE", "HEAD_POSE", "IDENTITY",
)
SIGNAL_METADATA_KEYS = {
    "FACE_PRESENCE": {"consecutive_absent_sec"},
    "MULTI_FACE": {"face_boxes"},
    "EYE_STATE": {"ear_left", "ear_right", "closed_duration_sec"},
    "MOUTH_STATE": {"mouth_open_ratio", "activity_ratio", "window_samples"},
    "OBJECT_PRESENCE": {"object_class", "bbox", "num_objects", "present_duration_sec"},
    "HEAD_POSE": {
        "yaw", "pitch", "roll", "away_duration_sec", "rotation_vector",
        "translation_vector", "camera_matrix", "nose_2d_px",
    },
    "IDENTITY": {"enrolled", "similarity", "warning", "consecutive_failures"},
}
NORMAL_SIGNAL_VALUES = {
    "FACE_PRESENCE": 1.0,
    "MULTI_FACE": 1.0,
    "EYE_STATE": 0.29,
    "MOUTH_STATE": 0.08,
    "OBJECT_PRESENCE": 0.0,
    "HEAD_POSE": 3.0,
    "IDENTITY": 0.82,
}
SCENARIO_WEIGHTS = {
    "low": (
        ("face_absent", 0.30), ("eyes_closed", 0.25), ("head_pose", 0.20),
        ("talking", 0.15), ("object", 0.05), ("multi_face", 0.04), ("identity", 0.01),
    ),
    "medium": (
        ("face_absent", 0.25), ("eyes_closed", 0.20), ("head_pose", 0.18),
        ("talking", 0.15), ("object", 0.12), ("multi_face", 0.07), ("identity", 0.03),
    ),
    "high": (
        ("face_absent", 0.18), ("eyes_closed", 0.15), ("head_pose", 0.12),
        ("talking", 0.12), ("object", 0.15), ("multi_face", 0.10),
        ("identity", 0.05), ("mixed_high", 0.13),
    ),
}
BROWSER_SEVERITY = {
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
PROFILE_WEIGHTS = (("normal", 0.20), ("low", 0.25), ("medium", 0.30), ("high", 0.25))
VIOLATION_RANGES = {
    "normal": (0, 0),
    "low": (5, 10),
    "medium": (12, 22),
    "high": (25, 40),
}
BROWSER_RANGES = {
    "normal": (0, 2),
    "low": (2, 5),
    "medium": (5, 10),
    "high": (10, 18),
}
FIRST_NAMES = (
    "An", "Bình", "Chi", "Dũng", "Giang", "Hà", "Hải", "Hiếu", "Hương", "Khánh",
    "Lan", "Linh", "Long", "Mai", "Minh", "Nam", "Ngân", "Ngọc", "Phương", "Quân",
    "Sơn", "Thảo", "Trang", "Trung", "Tuấn", "Vy",
)
LAST_NAMES = ("Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ")
MIDDLE_NAMES = (
    "Văn", "Thị", "Minh", "Ngọc", "Quốc", "Thanh", "Đức", "Thu", "Hoàng", "Anh",
    "Gia", "Hải", "Khánh", "Phương", "Quang", "Tuấn", "Hữu", "Bảo", "Mai", "Thùy",
)
EXAM_NAMES = (
    "Nhập môn Trí tuệ nhân tạo", "Cấu trúc dữ liệu và giải thuật",
    "Cơ sở dữ liệu", "Mạng máy tính", "Lập trình Python",
    "An toàn thông tin", "Xử lý ảnh số", "Kỹ thuật phần mềm",
    "Toán rời rạc", "Hệ điều hành", "Phân tích dữ liệu", "Điện toán đám mây",
)
STAFF_IDENTITIES = {
    "org_admin": (
        ("Nguyễn Minh Anh", "nguyen.minh.anh"),
        ("Trần Thu Hà", "tran.thu.ha"),
        ("Lê Quốc Bảo", "le.quoc.bao"),
    ),
    "manager": (
        ("Phạm Ngọc Lan", "pham.ngoc.lan"),
        ("Vũ Minh Quân", "vu.minh.quan"),
        ("Đặng Thùy Linh", "dang.thuy.linh"),
        ("Bùi Hoàng Nam", "bui.hoang.nam"),
    ),
    "proctor": (
        ("Đỗ Quang Hải", "do.quang.hai"),
        ("Nguyễn Mai Trang", "nguyen.mai.trang"),
        ("Trần Anh Dũng", "tran.anh.dung"),
        ("Lê Thanh Mai", "le.thanh.mai"),
        ("Phạm Đức Sơn", "pham.duc.son"),
    ),
}


@dataclass(frozen=True)
class Config:
    batch_id: str
    target_email: str
    exam_count: int
    session_count: int
    days: int
    seed: int
    org_admins: int
    managers: int
    proctors: int
    snapshot_rate: float
    sample_reports: int
    report_formats: tuple[str, ...]
    sessions_root: Path
    output_root: Path
    password: str
    dry_run: bool
    staff_domain: str
    student_domain: str
    exam_domain: str
    refresh_existing: bool
    regenerate_model_evidence: bool


@dataclass(frozen=True)
class BehaviorScenario:
    start_sec: float
    kind: str
    ordinal: int


@dataclass
class GenerationStats:
    organization_id: str = ""
    organization_name: str = ""
    users: list[dict[str, Any]] = field(default_factory=list)
    exams: list[dict[str, Any]] = field(default_factory=list)
    sessions: list[dict[str, Any]] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    browser_events: int = 0
    incident_reviews: int = 0
    snapshots: int = 0
    session_ids: list[str] = field(default_factory=list)
    report_jobs: int = 0
    reports: list[dict[str, str]] = field(default_factory=list)


def stable_id(batch_id: str, kind: str, key: str | int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{batch_id}:{kind}:{key}"))


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def choose_weighted(rng: random.Random, weighted: Sequence[tuple[str, float]]) -> str:
    marker = rng.random()
    total = 0.0
    for name, weight in weighted:
        total += weight
        if marker <= total:
            return name
    return weighted[-1][0]


def sanitize_batch_id(raw: str) -> str:
    value = raw.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,39}", value):
        raise argparse.ArgumentTypeError("batch-id phải dài 3-40 ký tự: a-z, 0-9, _ hoặc -")
    return value


def staff_identity(group: str, index: int, domain: str) -> tuple[str, str]:
    profiles = STAFF_IDENTITIES[group]
    display_name, local_part = profiles[index % len(profiles)]
    cycle = index // len(profiles)
    if cycle:
        local_part = f"{local_part}.{cycle + 1}"
    return display_name, f"{local_part}@{domain}"


def student_identity(index: int, domain: str) -> tuple[str, str, str]:
    """Return a deterministic, unique-enough Vietnamese student profile.

    The permutation spreads first/middle/last names across the dataset instead
    of visibly repeating the same short list every few rows.
    """
    combinations = len(LAST_NAMES) * len(MIDDLE_NAMES) * len(FIRST_NAMES)
    code = (index * 37) % combinations
    last_name = LAST_NAMES[code % len(LAST_NAMES)]
    code //= len(LAST_NAMES)
    middle_name = MIDDLE_NAMES[code % len(MIDDLE_NAMES)]
    code //= len(MIDDLE_NAMES)
    first_name = FIRST_NAMES[code % len(FIRST_NAMES)]
    display_name = f"{last_name} {middle_name} {first_name}"
    cohort = 21 + index % 5
    faculty = 1 + (index // 5) % 8
    candidate_number = f"{cohort:02d}{faculty:02d}{index + 1:04d}"
    return display_name, candidate_number, f"{candidate_number}@{domain}"


def exam_title(index: int, scheduled_start: datetime) -> str:
    semester = 1 if scheduled_start.month >= 8 or scheduled_start.month == 1 else 2
    academic_start = scheduled_start.year if scheduled_start.month >= 8 else scheduled_start.year - 1
    academic_year = f"{academic_start}–{academic_start + 1}"
    return f"Thi cuối kỳ - {EXAM_NAMES[index % len(EXAM_NAMES)]} - Học kỳ {semester}, {academic_year}"


def google_subject(batch_id: str, index: int) -> str:
    digest = hashlib.sha256(f"{batch_id}:google-subject:{index}".encode()).digest()
    return str(int.from_bytes(digest[:9], "big"))[:21]


def csv_write(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def jsonl_write(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def snapshot_bytes(severity: str) -> bytes:
    colors = {"LOW": "#15803d", "MEDIUM": "#d97706", "HIGH": "#b91c1c"}
    image = Image.new("RGB", (640, 360), colors[severity])
    draw = ImageDraw.Draw(image)
    draw.rectangle((25, 25, 615, 335), outline="white", width=4)
    draw.text((55, 125), "PROCTORING CAMERA RECORD", fill="white")
    draw.text((55, 165), f"Risk level: {severity}", fill="white")
    draw.text((55, 205), "Frame captured automatically", fill="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def build_scenarios(
    rng: random.Random,
    profile: str,
    duration_sec: float,
    desired_count: int,
) -> list[BehaviorScenario]:
    """Place non-overlapping behavior windows across one exam session."""
    capacity = max(0, int((duration_sec - 20.0) // 12.0))
    count = min(desired_count, capacity)
    if count <= 0:
        return []
    weights = SCENARIO_WEIGHTS.get(profile) or SCENARIO_WEIGHTS["medium"]
    usable = max(1.0, duration_sec - 20.0)
    scenarios: list[BehaviorScenario] = []
    for index in range(count):
        start = 10.0 + usable * (index + 1) / (count + 1)
        kind = choose_weighted(rng, weights)
        if kind in {"identity", "mixed_high"} and start < 32.0:
            kind = "face_absent"
        scenarios.append(BehaviorScenario(round(start, 3), kind, index))
    return scenarios


def scenario_conditions(
    video_time_sec: float,
    scenarios: Sequence[BehaviorScenario],
) -> tuple[dict[str, float], str | None]:
    """Return active signal ages and the current identity verification phase."""
    active: dict[str, float] = {}
    identity_phase: str | None = None

    def mark(name: str, age: float) -> None:
        active[name] = max(active.get(name, 0.0), max(0.0, age))

    for scenario in scenarios:
        offset = video_time_sec - scenario.start_sec
        if scenario.kind in {"identity", "mixed_high"} and -30.0 <= offset < 0.0:
            identity_phase = "first_failure"
        if not 0.0 <= offset <= 3.0:
            continue
        if scenario.kind == "face_absent":
            mark("FACE_PRESENCE", offset)
            if offset < 0.5:
                mark("HEAD_POSE", offset)
        elif scenario.kind == "multi_face":
            mark("MULTI_FACE", offset)
            if offset < 0.5:
                mark("EYE_STATE", offset)
        elif scenario.kind == "eyes_closed":
            for name in ("EYE_STATE", "MOUTH_STATE", "HEAD_POSE"):
                mark(name, offset)
        elif scenario.kind == "talking":
            for name in ("MOUTH_STATE", "HEAD_POSE"):
                mark(name, offset)
            if offset < 0.5:
                mark("EYE_STATE", offset)
        elif scenario.kind == "head_pose":
            mark("HEAD_POSE", offset)
            if offset < 0.5:
                mark("FACE_PRESENCE", offset)
                mark("MOUTH_STATE", offset)
        elif scenario.kind == "object":
            mark("OBJECT_PRESENCE", offset)
        elif scenario.kind == "identity":
            mark("IDENTITY", offset)
            identity_phase = "confirmed_mismatch"
        else:  # mixed_high: enough simultaneous SUSPICIOUS states for HIGH.
            for name in ("FACE_PRESENCE", "MULTI_FACE", "EYE_STATE", "OBJECT_PRESENCE", "IDENTITY"):
                mark(name, offset)
            identity_phase = "confirmed_mismatch"
    return active, identity_phase


def make_signal_results(
    rng: random.Random,
    timestamp: float,
    active: dict[str, float],
    identity_phase: str | None,
) -> list[SignalResult]:
    """Build all seven raw SignalResult objects using production metadata shapes."""
    results: list[SignalResult] = []
    for name in SIGNAL_NAMES:
        is_active = name in active
        age = active.get(name, 0.0)
        if name == "FACE_PRESENCE":
            value = 0.0 if is_active else 1.0
            confidence = 0.0 if is_active else round(rng.uniform(0.93, 0.998), 4)
            metadata = {"consecutive_absent_sec": round(age + 2.1, 2) if is_active else 0.0}
        elif name == "MULTI_FACE":
            count = rng.choice((2, 2, 2, 3)) if is_active else 1
            value = float(count)
            confidence = round(rng.uniform(0.91, 0.995), 4)
            metadata = {
                "face_boxes": [
                    [45.0 + box_index * 180.0, 36.0, 180.0 + box_index * 180.0, 240.0]
                    for box_index in range(count)
                ]
            }
        elif name == "EYE_STATE":
            if is_active:
                left = rng.uniform(0.12, 0.19)
                right = rng.uniform(0.12, 0.19)
            else:
                left = rng.uniform(0.24, 0.34)
                right = rng.uniform(0.24, 0.34)
            value = round((left + right) / 2.0, 4)
            confidence = 1.0
            metadata = {
                "ear_left": round(left, 4),
                "ear_right": round(right, 4),
                "closed_duration_sec": round(age + 1.1, 2) if is_active else 0.0,
            }
        elif name == "MOUTH_STATE":
            value = round(rng.uniform(0.18, 0.55) if is_active else rng.uniform(0.04, 0.13), 4)
            activity_ratio = rng.uniform(0.36, 0.9) if is_active else rng.uniform(0.0, 0.18)
            confidence = 1.0
            metadata = {
                "mouth_open_ratio": value,
                "activity_ratio": round(activity_ratio, 4),
                "window_samples": rng.randint(12, 32),
            }
        elif name == "OBJECT_PRESENCE":
            count = rng.choice((1, 1, 1, 2)) if is_active else 0
            value = float(count)
            confidence = round(rng.uniform(0.6, 0.98), 4) if is_active else 0.0
            object_class = rng.choice(("cell phone", "cell phone", "cell phone", "book")) if is_active else None
            metadata = {
                "object_class": object_class,
                "bbox": [220.0, 145.0, 355.0, 330.0] if is_active else None,
                "num_objects": count,
                "present_duration_sec": round(age + 1.1, 2) if is_active else 0.0,
            }
        elif name == "HEAD_POSE":
            if is_active and rng.random() < 0.75:
                yaw = rng.choice((-1.0, 1.0)) * rng.uniform(22.0, 55.0)
                pitch = rng.uniform(-12.0, 12.0)
            elif is_active:
                yaw = rng.uniform(-9.0, 9.0)
                pitch = rng.choice((-1.0, 1.0)) * rng.uniform(22.0, 42.0)
            else:
                yaw = rng.uniform(-8.0, 8.0)
                pitch = rng.uniform(-8.0, 8.0)
            value = round(yaw, 2)
            confidence = 1.0
            metadata = {
                "yaw": value,
                "pitch": round(pitch, 2),
                "roll": round(rng.uniform(-4.0, 4.0), 2),
                "away_duration_sec": round(age + 1.1, 2) if is_active else 0.0,
                "rotation_vector": [0.01, 0.02, 0.03],
                "translation_vector": [0.0, 0.0, 1000.0],
                "camera_matrix": [[640.0, 0.0, 320.0], [0.0, 640.0, 180.0], [0.0, 0.0, 1.0]],
                "nose_2d_px": [320.0, 180.0],
            }
        else:  # IDENTITY
            if identity_phase == "confirmed_mismatch":
                similarity = rng.uniform(0.16, 0.38)
                failures = 2
                exceeds = True
                warning = False
            elif identity_phase == "first_failure":
                similarity = rng.uniform(0.16, 0.38)
                failures = 1
                exceeds = False
                warning = False
            else:
                warning = rng.random() < 0.03
                similarity = rng.uniform(0.42, 0.54) if warning else rng.uniform(0.62, 0.9)
                failures = 0
                exceeds = False
            value = round(similarity, 4)
            confidence = 1.0
            metadata = {
                "enrolled": True,
                "similarity": value,
                "warning": warning,
                "consecutive_failures": failures,
            }
            results.append(SignalResult(name, timestamp, value, exceeds, confidence, metadata))
            continue
        results.append(SignalResult(name, timestamp, value, is_active, confidence, metadata))
    return results


def signal_log_record(result: SignalResult, video_time_sec: float, received_at: datetime) -> dict[str, Any]:
    record = dataclasses.asdict(result)
    record["client_timestamp"] = record.pop("timestamp")
    record["timestamp"] = received_at.timestamp()
    record["video_time_sec"] = round(video_time_sec, 3)
    record["server_received_at"] = iso(received_at)
    return record


def make_browser_events(
    rng: random.Random,
    config: Config,
    session_id: str,
    started_at: datetime,
    duration_sec: float,
    count: int,
) -> list[dict[str, Any]]:
    event_types = tuple(BROWSER_SEVERITY)
    if count <= 0:
        return []
    times = sorted(rng.uniform(5.0, max(6.0, duration_sec - 2.0)) for _ in range(count))
    rows: list[dict[str, Any]] = []
    for sequence, video_time in enumerate(times):
        event_type = rng.choice(event_types)
        timestamp = started_at + timedelta(seconds=video_time)
        duration_ms = rng.randint(800, 18_000) if event_type in {
            "TAB_HIDDEN", "WINDOW_BLUR", "TAB_SWITCHED", "FULLSCREEN_EXIT"
        } else None
        severity = BROWSER_SEVERITY[event_type]
        if duration_ms and duration_ms > 5_000:
            severity = "HIGH"
        rows.append({
            "event_id": stable_id(config.batch_id, "browser-event", f"{session_id}:{sequence}"),
            "sequence": sequence,
            "event_type": event_type,
            "client_timestamp": iso(timestamp - timedelta(milliseconds=rng.randint(20, 250))),
            "observed_origin": f"https://{config.exam_domain}",
            "duration_ms": duration_ms,
            "metadata": {"source": "browser_extension"},
            "timestamp": iso(timestamp),
            "video_time_sec": round(video_time, 3),
            "severity": severity,
            "server_duration_ms": duration_ms,
            "snapshot_path": None,
            "server_received_at": iso(timestamp),
        })
    return rows


def make_session_evidence(
    config: Config,
    rng: random.Random,
    session_id: str,
    student_name: str,
    candidate_number: str,
    candidate_email: str | None,
    authentication_method: str,
    client_type: str,
    extension_version: str | None,
    profile: str,
    started_at: datetime,
    ended_at: datetime | None,
    duration_sec: float,
    snapshot_payloads: dict[str, bytes],
    desired_violation_count: int | None = None,
    replace_existing: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]], int, int]:
    session_dir = config.sessions_root / session_id
    snapshot_dir = session_dir / "snapshots"
    if replace_existing:
        session_dir.mkdir(parents=True, exist_ok=True)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        for evidence_name in (
            "signals.jsonl", "state_transitions.jsonl", "violations.jsonl",
            "browser_events.jsonl", "risk_score_timeline.jsonl",
        ):
            path = session_dir / evidence_name
            if path.is_file():
                path.unlink()
        for snapshot in snapshot_dir.glob("evt_*.png"):
            snapshot.unlink()
    else:
        snapshot_dir.mkdir(parents=True, exist_ok=False)

    requested_count = (
        desired_violation_count
        if desired_violation_count is not None
        else rng.randint(*VIOLATION_RANGES[profile])
    )
    scenarios = build_scenarios(rng, profile, duration_sec, requested_count)
    tick_times = {round(value, 3) for value in range(0, max(1, int(duration_sec)) + 1, 30)}
    for scenario in scenarios:
        tick_times.update(
            round(scenario.start_sec + offset, 3)
            for offset in range(0, 11)
            if scenario.start_sec + offset <= duration_sec
        )
        if scenario.kind in {"identity", "mixed_high"}:
            tick_times.add(round(max(0.0, scenario.start_sec - 30.0), 3))

    violations: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    snapshots = 0
    transition_path = session_dir / "state_transitions.jsonl"
    risk_path = session_dir / "risk_score_timeline.jsonl"
    transition_logger = StateTransitionLogger(transition_path)
    risk_logger = RiskScoreLogger(risk_path)
    fusion = RiskFusionEngine.from_config(
        ROOT / "config" / "fusion.yaml",
        session_id=session_id,
        session_start_ts=started_at.timestamp(),
        logger=transition_logger,
        risk_score_logger=risk_logger,
    )
    try:
        for video_time in sorted(tick_times):
            observed_at = started_at + timedelta(seconds=video_time)
            active, identity_phase = scenario_conditions(video_time, scenarios)
            results = make_signal_results(
                rng, observed_at.timestamp(), active, identity_phase
            )
            signals.extend(signal_log_record(result, video_time, observed_at) for result in results)
            event = fusion.update(results, frame_bgr=None)
            if event is None:
                continue
            event_id = stable_id(config.batch_id, "violation", f"{session_id}:{len(violations)}")
            snapshot_path = None
            if rng.random() < config.snapshot_rate:
                filename = f"evt_{event_id}.png"
                (snapshot_dir / filename).write_bytes(snapshot_payloads[event.severity])
                snapshot_path = f"snapshots/{filename}"
                snapshots += 1
            event_at = started_at + timedelta(seconds=event.video_time_sec)
            event = dataclasses.replace(
                event,
                event_id=event_id,
                timestamp=iso(event_at),
                snapshot_path=snapshot_path,
                metadata={
                    "fusion_config_version": "v1",
                    "capture_source": "risk_fusion_engine",
                },
            )
            violations.append(dataclasses.asdict(event))
    finally:
        transition_logger.close()
        risk_logger.close()

    if len(violations) != len(scenarios):
        raise RuntimeError(
            f"Fusion engine sinh sai số event cho {session_id}: "
            f"{len(violations)} != {len(scenarios)}"
        )

    browser_count = rng.randint(*BROWSER_RANGES[profile]) if client_type == "browser_extension" else 0
    browser_events = make_browser_events(
        rng, config, session_id, started_at, duration_sec, browser_count
    )
    meta_end = ended_at or started_at + timedelta(seconds=duration_sec)
    meta = {
        "session_id": session_id,
        "started_at": iso(started_at),
        "ended_at": iso(meta_end) if ended_at else None,
        "duration_sec": round(duration_sec, 3),
        "fusion_config_version": "v1",
        "end_reason": "completed" if ended_at else None,
        "student_name": student_name,
        "candidate_number": candidate_number,
        "candidate_email": candidate_email,
        "authentication_method": authentication_method,
        "client_type": client_type,
        "extension_version": extension_version,
        "telemetry_sampling": {"baseline_interval_sec": 30, "event_interval_sec": 1},
    }
    (session_dir / "session_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    jsonl_write(session_dir / "signals.jsonl", signals)
    jsonl_write(session_dir / "violations.jsonl", violations)
    jsonl_write(session_dir / "browser_events.jsonl", browser_events)
    return meta, violations, browser_count, snapshots


def create_users(
    db: Any,
    config: Config,
    org: models.Organization,
    invited_by_user_id: str,
    password_hash: str,
) -> tuple[list[models.User], list[models.User], list[models.User], list[dict[str, Any]]]:
    groups: dict[str, list[models.User]] = {"org_admin": [], "manager": [], "proctor": []}
    rows: list[dict[str, Any]] = []
    counts = {"org_admin": config.org_admins, "manager": config.managers, "proctor": config.proctors}
    for group, count in counts.items():
        membership_role = "org_admin" if group == "org_admin" else "exam_manager"
        legacy_role = "admin" if group == "org_admin" else "proctor"
        for index in range(count):
            number = index + 1
            display_name, email = staff_identity(group, index, config.staff_domain)
            user_id = stable_id(config.batch_id, "user", f"{group}:{number}")
            if db.get(models.User, user_id) or db.query(models.User).filter_by(email=email).first():
                raise RuntimeError(f"Batch đã tồn tại hoặc email bị trùng: {email}")
            user = models.User(
                id=user_id,
                org_id=org.id,
                email=email,
                display_name=display_name,
                password_hash=password_hash,
                role=legacy_role,
                status="active",
                mfa_enabled=False,
            )
            db.add(user)
            db.flush()
            db.add(models.OrganizationMembership(
                id=stable_id(config.batch_id, "membership", f"{group}:{number}"),
                user_id=user.id,
                org_id=org.id,
                role=membership_role,
                status="active",
                invited_by_user_id=invited_by_user_id,
            ))
            groups[group].append(user)
            rows.append({
                "email": email,
                "password": config.password,
                "display_name": user.display_name,
                "organization_role": membership_role,
                "exam_role": "proctor" if group == "proctor" else ("owner/manager" if group == "manager" else "none"),
                "purpose": "Quản trị tổ chức" if group == "org_admin" else ("Quản lý kỳ thi" if group == "manager" else "Giám sát kỳ thi"),
            })
    return groups["org_admin"], groups["manager"], groups["proctor"], rows


def exam_status(index: int, exam_count: int) -> str:
    if index == 0:
        return "draft"
    if index == 1 and exam_count >= 5:
        return "scheduled"
    if index in {exam_count - 2, exam_count - 1}:
        return "open"
    if index == 2 and exam_count >= 6:
        return "archived"
    return "closed"


def make_join_code(batch_id: str, index: int) -> str:
    digest = hashlib.sha256(f"{batch_id}:exam:{index}".encode()).hexdigest().upper()
    return digest[:10]


def create_exams_and_assignments(
    db: Any,
    config: Config,
    org: models.Organization,
    managers: list[models.User],
    proctors: list[models.User],
    now: datetime,
) -> tuple[list[models.Exam], list[dict[str, Any]]]:
    exams: list[models.Exam] = []
    exam_rows: list[dict[str, Any]] = []
    for index in range(config.exam_count):
        owner = managers[index % len(managers)]
        status = exam_status(index, config.exam_count)
        exam_id = stable_id(config.batch_id, "exam", index)
        if db.get(models.Exam, exam_id):
            raise RuntimeError(f"Batch đã tồn tại: exam {exam_id}")
        if status == "scheduled":
            scheduled_start = now + timedelta(days=7)
        elif status in {"open", "draft"}:
            scheduled_start = now - timedelta(hours=1)
        else:
            scheduled_start = now - timedelta(days=max(1, config.days * (index + 1) / config.exam_count))
        scheduled_end = scheduled_start + timedelta(hours=2)
        exam = models.Exam(
            id=exam_id,
            org_id=org.id,
            name=exam_title(index, scheduled_start),
            join_code=make_join_code(config.batch_id, index),
            status=status,
            join_code_expires_at=now + timedelta(days=30),
            candidate_auth_mode="google" if index % 3 == 0 else "manual",
            exam_url=f"https://{config.exam_domain}/exams/{make_join_code(config.batch_id, index).lower()}",
            require_extension=index % 2 == 0,
            min_extension_version="1.0.0",
            require_fullscreen=True,
            require_camera=True,
            require_microphone=index % 3 == 0,
            require_screen_share=index % 4 == 0,
            block_clipboard=True,
            max_focus_loss_seconds=5.0,
            google_allowed_domain=config.student_domain if index % 3 == 0 else None,
            created_by_user_id=owner.id,
            owner_user_id=owner.id,
            scheduled_start_at=scheduled_start,
            scheduled_end_at=scheduled_end,
            archived_at=now - timedelta(days=2) if status == "archived" else None,
            created_at=scheduled_start - timedelta(days=14),
            updated_at=now,
        )
        db.add(exam)
        db.flush()
        assignment_specs: list[tuple[models.User, str]] = [(owner, "owner")]
        assignment_specs.append((managers[(index + 1) % len(managers)], "manager"))
        if len(managers) > 2 and index % 2 == 0:
            assignment_specs.append((managers[(index + 2) % len(managers)], "manager"))
        assignment_specs.extend((proctors[(index + offset) % len(proctors)], "proctor") for offset in range(min(2, len(proctors))))
        seen: set[str] = set()
        assigned_labels: list[str] = []
        for user, role in assignment_specs:
            if user.id in seen:
                continue
            seen.add(user.id)
            db.add(models.ExamAssignment(
                id=stable_id(config.batch_id, "assignment", f"{exam.id}:{user.id}"),
                exam_id=exam.id,
                user_id=user.id,
                assignment_role=role,
                status="active",
                assigned_by_user_id=owner.id,
                is_pinned=role == "owner" and index < 4,
                pinned_at=now if role == "owner" and index < 4 else None,
            ))
            assigned_labels.append(f"{user.email}:{role}")
        db.add(models.AuditLog(
            id=stable_id(config.batch_id, "audit", f"exam-create:{index}"),
            actor_user_id=owner.id,
            actor_role="exam_manager",
            org_id=org.id,
            exam_id=exam.id,
            action="exam.create",
            resource_type="exam",
            resource_id=exam.id,
            outcome="success",
            reason="Khởi tạo kỳ thi theo kế hoạch đào tạo",
            after_json=json.dumps({"status": status}, ensure_ascii=False),
            created_at=exam.created_at,
        ))
        exams.append(exam)
        exam_rows.append({
            "exam_id": exam.id,
            "exam_name": exam.name,
            "status": status,
            "owner_email": owner.email,
            "candidate_auth_mode": exam.candidate_auth_mode,
            "scheduled_start_at": iso(scheduled_start),
            "scheduled_end_at": iso(scheduled_end),
            "assignments": "; ".join(assigned_labels),
        })
    return exams, exam_rows


def create_candidate_identities(db: Any, config: Config, now: datetime) -> list[models.CandidateIdentity]:
    pool_size = max(50, min(config.session_count, (config.session_count // max(1, config.exam_count)) + 20))
    identities: list[models.CandidateIdentity] = []
    for index in range(pool_size):
        candidate_id = stable_id(config.batch_id, "candidate", index)
        display_name, candidate_number, email = student_identity(index, config.student_domain)
        identity = models.CandidateIdentity(
            id=candidate_id,
            provider="google",
            provider_subject=google_subject(config.batch_id, index),
            email=email,
            email_verified=True,
            display_name=display_name,
            hosted_domain=config.student_domain,
            created_at=now - timedelta(days=config.days),
            updated_at=now,
            last_login_at=now - timedelta(days=index % max(1, config.days)),
        )
        db.add(identity)
        db.flush()
        db.add(models.CandidateDevice(
            id=stable_id(config.batch_id, "candidate-device", index),
            candidate_identity_id=identity.id,
            device_id_hash=hashlib.sha256(f"{config.batch_id}:device:{index}".encode()).hexdigest(),
            token_hash=hashlib.sha256(f"{config.batch_id}:token:{index}".encode()).hexdigest(),
            created_at=identity.created_at,
            last_used_at=identity.last_login_at,
            expires_at=now + timedelta(days=365),
        ))
        identities.append(identity)
    return identities


def active_exam_indices(exams: Sequence[models.Exam]) -> list[int]:
    indices = [index for index, exam in enumerate(exams) if exam.status not in {"draft", "scheduled"}]
    return indices or list(range(len(exams)))


def create_sessions(
    db: Any,
    config: Config,
    org: models.Organization,
    exams: list[models.Exam],
    identities: list[models.CandidateIdentity],
    managers: list[models.User],
    proctors: list[models.User],
    now: datetime,
    stats: GenerationStats,
) -> None:
    snapshot_payloads = {severity: snapshot_bytes(severity) for severity in ("LOW", "MEDIUM", "HIGH")}
    eligible_exam_indices = active_exam_indices(exams)
    sessions_per_exam: Counter[int] = Counter()
    reviewed_audits = 0
    for index in range(config.session_count):
        rng = random.Random(config.seed * 1_000_003 + index)
        exam_index = eligible_exam_indices[index % len(eligible_exam_indices)]
        exam = exams[exam_index]
        ordinal = sessions_per_exam[exam_index]
        sessions_per_exam[exam_index] += 1
        session_id = stable_id(config.batch_id, "session", index)
        if db.get(models.ExamSession, session_id) or (config.sessions_root / session_id).exists():
            raise RuntimeError(f"Batch đã tồn tại hoặc thư mục phiên bị trùng: {session_id}")
        profile = choose_weighted(rng, PROFILE_WEIGHTS)
        student_name, candidate_number, student_email = student_identity(ordinal, config.student_domain)
        uses_google = exam.candidate_auth_mode == "google" and ordinal < len(identities)
        identity = identities[ordinal % len(identities)] if uses_google else None
        candidate_email = identity.email if identity else student_email
        authentication_method = "google" if identity else "manual"
        client_type = "browser_extension" if exam.require_extension or index % 3 != 0 else "desktop_cv"
        extension_version = rng.choice(("1.0.0", "1.1.0", "1.2.0")) if client_type == "browser_extension" else None

        is_open = exam.status == "open"
        live_slot = index % 50
        if is_open and live_slot == 0:
            status = "active"
            started_at = now - timedelta(seconds=rng.randint(5, 45))
            duration_sec = max(10.0, (now - started_at).total_seconds())
            ended_at = None
            last_seen_at = now - timedelta(seconds=rng.randint(0, 5))
            disconnect_reason = None
        elif is_open and live_slot == 1:
            status = "pending"
            started_at = now - timedelta(seconds=rng.randint(5, 45))
            duration_sec = max(10.0, (now - started_at).total_seconds())
            ended_at = None
            last_seen_at = started_at
            disconnect_reason = None
        else:
            days_ago = rng.uniform(1.0, float(config.days))
            started_at = now - timedelta(days=days_ago, hours=rng.uniform(0, 18))
            duration_sec = float(rng.randint(45, 120) * 60)
            ended_at = started_at + timedelta(seconds=duration_sec)
            if index % 25 == 0:
                status = "disconnected"
                disconnect_reason = rng.choice(("network_timeout", "browser_closed", "client_idle_timeout"))
            else:
                status = "ended"
                disconnect_reason = "completed"
            last_seen_at = ended_at - timedelta(seconds=rng.randint(0, 30))

        # Register the exact target before filesystem materialization so a
        # failure while writing the first file of this session is recoverable.
        stats.session_ids.append(session_id)
        meta, violations, browser_count, snapshots = make_session_evidence(
            config, rng, session_id, student_name, candidate_number, candidate_email,
            authentication_method, client_type, extension_version, profile,
            started_at, ended_at, duration_sec, snapshot_payloads,
        )
        integrity_score = min(100.0, sum(
            20.0 if event["severity"] == "HIGH" else 5.0 if event["severity"] == "MEDIUM" else 0.0
            for event in _read_jsonl(config.sessions_root / session_id / "browser_events.jsonl")
        ))
        integrity_status = "alert" if integrity_score >= 20 else "warning" if integrity_score >= 5 else "healthy"
        peak_risk = max((event["risk_score"] for event in violations), default=round(rng.uniform(0, 2.4), 2))
        session_state = "SESSION_ALERT" if status == "active" and peak_risk >= 5 else "SESSION_NORMAL"
        exam_session = models.ExamSession(
            id=session_id,
            exam_id=exam.id,
            student_name=student_name,
            candidate_number=candidate_number,
            candidate_email=candidate_email,
            candidate_identity_id=identity.id if identity else None,
            authentication_method=authentication_method,
            client_type=client_type,
            extension_version=extension_version,
            browser_name=rng.choice(("Chrome", "Firefox", "Edge")) if client_type == "browser_extension" else None,
            browser_version=str(rng.randint(124, 140)) if client_type == "browser_extension" else None,
            platform=rng.choice(("Windows 11", "Ubuntu 24.04", "macOS 15")),
            capabilities_json=json.dumps(["camera", "content_monitor", "storage_session"] if client_type == "browser_extension" else ["camera"]),
            device_id_hash=hashlib.sha256(f"{config.batch_id}:{session_id}".encode()).hexdigest(),
            camera_status="ready",
            microphone_status="ready" if exam.require_microphone else "not_required",
            screen_share_status="ready" if exam.require_screen_share else "not_required",
            reset_count=1 if index % 97 == 0 else 0,
            last_reset_at=started_at - timedelta(minutes=3) if index % 97 == 0 else None,
            last_reset_reason="Mất kết nối trước khi bắt đầu" if index % 97 == 0 else None,
            status=status,
            risk_score_current=peak_risk,
            session_state_current=session_state,
            started_at=started_at,
            ended_at=ended_at,
            last_seen_at=last_seen_at,
            disconnect_reason=disconnect_reason,
            integrity_score_current=integrity_score,
            integrity_status_current=integrity_status,
            browser_event_count=browser_count,
        )
        db.add(exam_session)
        db.flush()

        for violation_index, violation in enumerate(violations):
            if rng.random() > 0.55:
                review_status = "new"
                reviewer = None
                reviewed_at = None
                note = None
            else:
                review_status = rng.choices(
                    ("new", "in_review", "confirmed", "dismissed"), weights=(20, 20, 40, 20), k=1
                )[0]
                reviewer = rng.choice(proctors + managers) if review_status != "new" else None
                reviewed_at = (started_at + timedelta(seconds=violation["video_time_sec"] + 120)) if reviewer else None
                note = {
                    "in_review": "Đang đối chiếu bằng chứng và nhật ký trình duyệt.",
                    "confirmed": "Đã xác nhận sự kiện cần ghi nhận trong biên bản.",
                    "dismissed": "Loại trừ sau khi giám thị kiểm tra ngữ cảnh.",
                }.get(review_status)
            if review_status != "new":
                review = models.IncidentReview(
                    id=stable_id(config.batch_id, "review", f"{session_id}:{violation_index}"),
                    exam_session_id=session_id,
                    violation_event_id=violation["event_id"],
                    status=review_status,
                    note=note,
                    reviewed_by_user_id=reviewer.id if reviewer else None,
                    created_at=started_at + timedelta(seconds=violation["video_time_sec"]),
                    updated_at=reviewed_at or started_at,
                    reviewed_at=reviewed_at,
                )
                db.add(review)
                stats.incident_reviews += 1
                if reviewed_audits < 250:
                    db.add(models.AuditLog(
                        id=stable_id(config.batch_id, "audit-review", f"{session_id}:{violation_index}"),
                        actor_user_id=reviewer.id if reviewer else None,
                        actor_role="proctor" if reviewer in proctors else "exam_manager",
                        org_id=org.id,
                        exam_id=exam.id,
                        action="exam.incident.review",
                        resource_type="violation_event",
                        resource_id=violation["event_id"],
                        outcome="success",
                        reason="Cập nhật kết quả rà soát sự kiện",
                        after_json=json.dumps({"status": review_status}),
                        created_at=reviewed_at or started_at,
                    ))
                    reviewed_audits += 1

            stats.violations.append({
                "exam_id": exam.id,
                "session_id": session_id,
                "event_id": violation["event_id"],
                "student_name": student_name,
                "profile": profile,
                "video_time_sec": violation["video_time_sec"],
                "violation_type": violation["primary_violation"],
                "severity": violation["severity"],
                "risk_score": violation["risk_score"],
                "review_status": review_status,
                "timestamp": violation["timestamp"],
            })
        stats.browser_events += browser_count
        stats.snapshots += snapshots
        stats.sessions.append({
            "session_id": session_id,
            "exam_id": exam.id,
            "exam_name": exam.name,
            "student_name": student_name,
            "candidate_number": candidate_number,
            "candidate_email": candidate_email,
            "authentication_method": authentication_method,
            "client_type": client_type,
            "status": status,
            "risk_profile": profile,
            "risk_score_peak": peak_risk,
            "integrity_score": integrity_score,
            "violation_count": len(violations),
            "browser_event_count": browser_count,
            "started_at": iso(started_at),
            "ended_at": meta["ended_at"],
            "duration_sec": duration_sec,
        })


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_session_evidence(session_dir: Path) -> dict[str, int]:
    """Validate generated evidence against the production model contracts."""
    signals = _read_jsonl(session_dir / "signals.jsonl")
    transitions = _read_jsonl(session_dir / "state_transitions.jsonl")
    violations = _read_jsonl(session_dir / "violations.jsonl")
    risk_rows = _read_jsonl(session_dir / "risk_score_timeline.jsonl")

    signals_by_time: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in signals:
        if "state" in row:
            raise RuntimeError(f"SignalResult không được chứa state: {session_dir.name}")
        signal_name = row.get("signal_name")
        if signal_name not in SIGNAL_NAMES:
            raise RuntimeError(f"Signal không hợp lệ trong {session_dir.name}: {signal_name}")
        missing_metadata = SIGNAL_METADATA_KEYS[signal_name] - set(row.get("metadata", {}))
        if missing_metadata:
            raise RuntimeError(
                f"{signal_name} thiếu metadata {sorted(missing_metadata)} trong {session_dir.name}"
            )
        signals_by_time[float(row["video_time_sec"])].append(row)
    for video_time, rows in signals_by_time.items():
        names = {row["signal_name"] for row in rows}
        if len(rows) != len(SIGNAL_NAMES) or names != set(SIGNAL_NAMES):
            raise RuntimeError(
                f"Telemetry {session_dir.name}@{video_time} không đủ đúng 7 signal"
            )

    legal_signal_transitions = {
        ("NORMAL", "SUSPICIOUS"),
        ("SUSPICIOUS", "ALERT"),
        ("SUSPICIOUS", "NORMAL"),
        ("ALERT", "SUSPICIOUS"),
    }
    for row in transitions:
        if row.get("scope") == "signal" and (
            row.get("from_state"), row.get("to_state")
        ) not in legal_signal_transitions:
            raise RuntimeError(f"Transition signal không hợp lệ trong {session_dir.name}: {row}")

    thresholds = load_session_thresholds(ROOT / "config" / "fusion.yaml")
    state_value = {"SUSPICIOUS": 1, "ALERT": 2}
    risk_by_time = {float(row["video_time_sec"]): float(row["risk_score"]) for row in risk_rows}
    for event in violations:
        contributions = event.get("contributing_signals", [])
        if not contributions:
            raise RuntimeError(f"Violation không có contributing signal: {event.get('event_id')}")
        computed = sum(
            float(item["weight"]) * state_value[item["state"]]
            for item in contributions
        )
        if abs(computed - float(event["risk_score"])) > 1e-6:
            raise RuntimeError(
                f"Risk score sai ở {event.get('event_id')}: {event['risk_score']} != {computed}"
            )
        primary = max(
            contributions,
            key=lambda item: float(item["weight"]) * state_value[item["state"]],
        )["violation_type"]
        if event.get("primary_violation") != primary:
            raise RuntimeError(f"Primary violation sai ở {event.get('event_id')}")
        if computed < thresholds.t_enter:
            raise RuntimeError(f"Violation dưới T_enter: {event.get('event_id')}")
        expected_severity = "HIGH" if computed >= thresholds.severity_high_min else "MEDIUM"
        if event.get("severity") != expected_severity:
            raise RuntimeError(f"Severity sai ở {event.get('event_id')}")
        logged_risk = risk_by_time.get(float(event["video_time_sec"]))
        if logged_risk is None or abs(logged_risk - computed) > 1e-6:
            raise RuntimeError(f"Risk timeline không khớp event {event.get('event_id')}")

    if len(risk_rows) != len(signals_by_time):
        raise RuntimeError(f"Risk timeline không phủ đủ telemetry trong {session_dir.name}")
    return {
        "signal_rows": len(signals),
        "signal_ticks": len(signals_by_time),
        "transitions": len(transitions),
        "violations": len(violations),
        "risk_rows": len(risk_rows),
    }


def refresh_output_files(
    config: Config,
    database_backup: Path | None,
    email_map: dict[str, str],
    staff_by_email: dict[str, dict[str, str]],
    exam_updates: dict[str, dict[str, str]],
    session_updates: dict[str, dict[str, str]],
) -> Path:
    output_dir = config.output_root / config.batch_id
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Không tìm thấy manifest của batch: {manifest_path}")
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    backup_dir = config.output_root / f"{config.batch_id}-pre-refresh-{stamp}"
    shutil.copytree(output_dir, backup_dir)

    account_rows = _read_csv(output_dir / "accounts.csv")
    for row in account_rows:
        row["email"] = email_map.get(row["email"], row["email"])
        profile = staff_by_email.get(row["email"])
        if profile:
            row["display_name"] = profile["display_name"]
    csv_write(output_dir / "accounts.csv", tuple(account_rows[0]), account_rows)

    exam_rows = _read_csv(output_dir / "exams.csv")
    for row in exam_rows:
        update = exam_updates.get(row["exam_id"])
        if update:
            row["exam_name"] = update["exam_name"]
            row["owner_email"] = email_map.get(row["owner_email"], row["owner_email"])
            assignments = row.get("assignments", "")
            for old_email, new_email in email_map.items():
                assignments = assignments.replace(old_email, new_email)
            row["assignments"] = assignments
    csv_write(output_dir / "exams.csv", tuple(exam_rows[0]), exam_rows)

    session_rows = _read_csv(output_dir / "sessions.csv")
    for row in session_rows:
        update = session_updates.get(row["session_id"])
        if update:
            row.update(update)
    csv_write(output_dir / "sessions.csv", tuple(session_rows[0]), session_rows)

    violation_rows = _read_csv(output_dir / "violations.csv")
    for row in violation_rows:
        update = session_updates.get(row["session_id"])
        if update:
            row["student_name"] = update["student_name"]
    csv_write(output_dir / "violations.csv", tuple(violation_rows[0]), violation_rows)

    exam_summary_rows = _read_csv(output_dir / "exam_summary.csv")
    for row in exam_summary_rows:
        update = exam_updates.get(row["exam_id"])
        if update:
            row["exam_name"] = update["exam_name"]
            row["owner_email"] = email_map.get(row["owner_email"], row["owner_email"])
    csv_write(output_dir / "exam_summary.csv", tuple(exam_summary_rows[0]), exam_summary_rows)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["refreshed_at"] = iso(utc_now())
    manifest["display_profile"] = "realistic_v1"
    manifest["refresh_database_backup"] = str(database_backup) if database_backup else None
    manifest["refresh_output_backup"] = str(backup_dir)
    manifest["configuration"].update({
        "staff_domain": config.staff_domain,
        "student_domain": config.student_domain,
        "exam_domain": config.exam_domain,
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup_dir


def refresh_existing_dataset(config: Config) -> tuple[dict[str, int], Path | None, Path]:
    """Refresh display data for one deterministic batch without changing IDs/counts."""
    output_dir = config.output_root / config.batch_id
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Không tìm thấy batch hiện có: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_sessions = int(manifest.get("counts", {}).get("sessions", config.session_count))
    if expected_sessions != config.session_count:
        raise RuntimeError(
            f"session-count phải khớp manifest hiện có: {config.session_count} != {expected_sessions}"
        )
    Base.metadata.create_all(bind=engine)
    apply_additive_migrations(engine)
    database_backup = backup_sqlite_database(f"{config.batch_id}-pre-refresh")
    snapshot_payloads = {severity: snapshot_bytes(severity) for severity in ("LOW", "MEDIUM", "HIGH")}
    email_map: dict[str, str] = {}
    staff_by_email: dict[str, dict[str, str]] = {}
    exam_updates: dict[str, dict[str, str]] = {}
    session_updates: dict[str, dict[str, str]] = {}
    refreshed_snapshots = 0
    output_backup: Path | None = None

    with SessionLocal() as db:
        target_user = db.query(models.User).filter(models.User.email == config.target_email).first()
        if target_user is None:
            raise RuntimeError(f"Không tìm thấy tài khoản mục tiêu: {config.target_email}")
        membership = db.query(models.OrganizationMembership).filter_by(
            user_id=target_user.id, org_id=target_user.org_id, status="active"
        ).first()
        if membership is None:
            raise RuntimeError("Tài khoản mục tiêu không có membership hoạt động")
        org = db.get(models.Organization, membership.org_id)
        if org is None:
            raise RuntimeError("Không tìm thấy tổ chức của tài khoản mục tiêu")

        for group, count in (
            ("org_admin", config.org_admins), ("manager", config.managers), ("proctor", config.proctors)
        ):
            for index in range(count):
                user_id = stable_id(config.batch_id, "user", f"{group}:{index + 1}")
                user = db.get(models.User, user_id)
                if user is None or user.org_id != org.id:
                    raise RuntimeError(f"Không tìm thấy user của batch: {user_id}")
                display_name, new_email = staff_identity(group, index, config.staff_domain)
                collision = db.query(models.User).filter(
                    models.User.email == new_email, models.User.id != user.id
                ).first()
                if collision:
                    raise RuntimeError(f"Email thực tế đã được dùng bởi tài khoản khác: {new_email}")
                email_map[user.email] = new_email
                user.email = new_email
                user.display_name = display_name
                staff_by_email[new_email] = {"display_name": display_name, "group": group}

        exams: list[models.Exam] = []
        for index in range(config.exam_count):
            exam = db.get(models.Exam, stable_id(config.batch_id, "exam", index))
            if exam is None or exam.org_id != org.id:
                raise RuntimeError(f"Không tìm thấy kỳ thi thứ {index + 1} của batch")
            start = exam.scheduled_start_at or exam.created_at
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            exam.name = exam_title(index, start)
            exam.exam_url = f"https://{config.exam_domain}/exams/{exam.join_code.lower()}"
            exam.google_allowed_domain = config.student_domain if exam.candidate_auth_mode == "google" else None
            exam.updated_at = utc_now()
            exams.append(exam)
            owner = db.get(models.User, exam.owner_user_id) if exam.owner_user_id else None
            exam_updates[exam.id] = {
                "exam_name": exam.name,
                "owner_email": owner.email if owner else "",
            }
            audit = db.get(models.AuditLog, stable_id(config.batch_id, "audit", f"exam-create:{index}"))
            if audit:
                audit.action = "exam.create"
                audit.reason = "Khởi tạo kỳ thi theo kế hoạch đào tạo"
                audit.after_json = json.dumps({"status": exam.status}, ensure_ascii=False)

        pool_size = max(50, min(config.session_count, (config.session_count // max(1, config.exam_count)) + 20))
        identities: list[models.CandidateIdentity] = []
        for index in range(pool_size):
            identity = db.get(models.CandidateIdentity, stable_id(config.batch_id, "candidate", index))
            if identity is None:
                raise RuntimeError(f"Không tìm thấy candidate identity thứ {index + 1}")
            display_name, _, email = student_identity(index, config.student_domain)
            identity.provider_subject = google_subject(config.batch_id, index)
            identity.email = email
            identity.display_name = display_name
            identity.hosted_domain = config.student_domain
            identity.updated_at = utc_now()
            identities.append(identity)

        eligible_exam_indices = active_exam_indices(exams)
        for index in range(config.session_count):
            session_id = stable_id(config.batch_id, "session", index)
            exam_index = eligible_exam_indices[index % len(eligible_exam_indices)]
            ordinal = index // len(eligible_exam_indices)
            student_name, candidate_number, student_email = student_identity(ordinal, config.student_domain)
            exam_session = db.get(models.ExamSession, session_id)
            if exam_session is None or exam_session.exam_id != exams[exam_index].id:
                raise RuntimeError(f"Không tìm thấy hoặc sai kỳ thi của phiên: {session_id}")
            identity = identities[ordinal % len(identities)] if exam_session.authentication_method == "google" else None
            candidate_email = identity.email if identity else student_email
            exam_session.student_name = student_name
            exam_session.candidate_number = candidate_number
            exam_session.candidate_email = candidate_email
            exam_session.candidate_identity_id = identity.id if identity else None
            session_updates[session_id] = {
                "exam_name": exams[exam_index].name,
                "student_name": student_name,
                "candidate_number": candidate_number,
                "candidate_email": candidate_email,
            }

            session_dir = config.sessions_root / session_id
            meta_path = session_dir / "session_meta.json"
            if not meta_path.is_file():
                raise RuntimeError(f"Phiên thiếu session_meta.json: {session_id}")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta.update({
                "student_name": student_name,
                "candidate_number": candidate_number,
                "candidate_email": candidate_email,
            })
            for key in ("synthetic", "batch_id", "risk_profile"):
                meta.pop(key, None)
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            violations_path = session_dir / "violations.jsonl"
            violations = _read_jsonl(violations_path)
            severity_by_snapshot: dict[str, str] = {}
            for violation in violations:
                violation["metadata"] = {
                    "fusion_config_version": str(violation.get("metadata", {}).get("fusion_config_version", "v1")),
                    "capture_source": "risk_fusion_engine",
                }
                snapshot_path = violation.get("snapshot_path")
                if snapshot_path:
                    severity_by_snapshot[Path(str(snapshot_path)).name] = str(violation.get("severity", "MEDIUM"))
            jsonl_write(violations_path, violations)

            browser_path = session_dir / "browser_events.jsonl"
            browser_events = _read_jsonl(browser_path)
            for event in browser_events:
                event["observed_origin"] = f"https://{config.exam_domain}"
                event["metadata"] = {"source": "browser_extension"}
            jsonl_write(browser_path, browser_events)

            snapshot_dir = session_dir / "snapshots"
            for filename, severity in severity_by_snapshot.items():
                target = snapshot_dir / filename
                if target.is_file():
                    target.write_bytes(snapshot_payloads.get(severity, snapshot_payloads["MEDIUM"]))
                    refreshed_snapshots += 1

        exam_ids = [exam.id for exam in exams]
        legacy_audits = db.query(models.AuditLog).filter(
            models.AuditLog.exam_id.in_(exam_ids),
            models.AuditLog.action == "exam.incident.review.synthetic",
        ).all()
        for audit in legacy_audits:
            audit.action = "exam.incident.review"
            audit.reason = "Cập nhật kết quả rà soát sự kiện"

        output_backup = refresh_output_files(
            config, database_backup, email_map, staff_by_email, exam_updates, session_updates
        )
        report_formats_by_session: dict[str, set[str]] = defaultdict(set)
        for report in manifest.get("reports", []):
            if report.get("format") in {"html", "pdf"}:
                report_formats_by_session[str(report["session_id"])].add(str(report["format"]))
        for session_id, formats in report_formats_by_session.items():
            generate_report(
                config.sessions_root / session_id,
                fusion_config_path=ROOT / "config" / "fusion.yaml",
                output_dir=config.sessions_root / session_id,
                formats=sorted(formats),
            )
        db.commit()

        counts = {
            "users": config.org_admins + config.managers + config.proctors,
            "exams": len(exams),
            "sessions": config.session_count,
            "snapshots": refreshed_snapshots,
            "legacy_audit_actions": db.query(models.AuditLog).filter(
                models.AuditLog.exam_id.in_(exam_ids),
                models.AuditLog.action.like("%.synthetic"),
            ).count(),
        }
    assert output_backup is not None
    return counts, database_backup, output_backup


def _backup_batch_evidence(config: Config, session_ids: Sequence[str], stamp: str) -> Path:
    archive_path = config.output_root / f"{config.batch_id}-pre-model-evidence-{stamp}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for session_id in session_ids:
            session_dir = config.sessions_root / session_id
            for path in session_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, Path(session_id) / path.relative_to(session_dir))
    return archive_path


def _rewrite_existing_batch_outputs(
    config: Config,
    stats: GenerationStats,
    manifest: dict[str, Any],
    database_backup: Path | None,
    output_backup: Path,
    evidence_backup: Path,
) -> None:
    output_dir = config.output_root / config.batch_id
    csv_write(
        output_dir / "sessions.csv",
        ("session_id", "exam_id", "exam_name", "student_name", "candidate_number", "candidate_email", "authentication_method", "client_type", "status", "risk_profile", "risk_score_peak", "integrity_score", "violation_count", "browser_event_count", "started_at", "ended_at", "duration_sec"),
        stats.sessions,
    )
    csv_write(
        output_dir / "violations.csv",
        ("exam_id", "session_id", "event_id", "student_name", "profile", "video_time_sec", "violation_type", "severity", "risk_score", "review_status", "timestamp"),
        stats.violations,
    )
    exam_summary, violation_summary, daily_summary = aggregate_rows(stats)
    csv_write(output_dir / "exam_summary.csv", tuple(exam_summary[0]), exam_summary)
    csv_write(
        output_dir / "violation_summary.csv",
        ("violation_type", "severity", "review_status", "count"),
        violation_summary,
    )
    csv_write(
        output_dir / "daily_summary.csv",
        ("date", "sessions", "violations", "browser_events", "high_risk_sessions"),
        daily_summary,
    )
    manifest["model_evidence_regenerated_at"] = iso(utc_now())
    manifest["model_evidence_profile"] = "risk_fusion_engine_v1"
    manifest["telemetry_sampling"] = {
        "baseline_interval_sec": 30,
        "event_interval_sec": 1,
        "signals_per_tick": len(SIGNAL_NAMES),
    }
    manifest["model_evidence_database_backup"] = str(database_backup) if database_backup else None
    manifest["model_evidence_output_backup"] = str(output_backup)
    manifest["model_evidence_archive"] = str(evidence_backup)
    manifest["counts"].update({
        "sessions": len(stats.sessions),
        "violations": len(stats.violations),
        "browser_events": stats.browser_events,
        "incident_reviews": stats.incident_reviews,
        "snapshots": stats.snapshots,
    })
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "README.md").write_text(
        f"""# Bộ dữ liệu báo cáo `{config.batch_id}`

- Tổ chức: **{stats.organization_name}**
- Tài khoản: **{len(stats.users)}** (`accounts.csv`)
- Kỳ thi: **{len(stats.exams)}**
- Phiên thi: **{len(stats.sessions)}**
- Vi phạm CV: **{len(stats.violations)}**
- Sự kiện trình duyệt: **{stats.browser_events}**
- Incident review đã lưu: **{stats.incident_reviews}**

Evidence model được sinh bởi `RiskFusionEngine` theo `config/fusion.yaml`.
Telemetry có đủ 7 signal mỗi tick, lấy mẫu nền mỗi 30 giây và mỗi giây trong
cửa sổ hành vi. Đây là dữ liệu tổng hợp để kiểm thử dashboard/báo cáo, không
phải ground truth dùng để đánh giá độ chính xác model trên video thật.

Các file `exam_summary.csv`, `daily_summary.csv` và `violation_summary.csv` có
thể nhập trực tiếp vào Excel/Google Sheets để dựng bảng và biểu đồ báo cáo.
`sessions.csv` và `violations.csv` chứa dữ liệu chi tiết.
""",
        encoding="utf-8",
    )


def regenerate_existing_model_evidence(
    config: Config,
) -> tuple[dict[str, int], Path | None, Path, Path]:
    """Regenerate an existing batch with production RiskFusionEngine semantics."""
    output_dir = config.output_root / config.batch_id
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Không tìm thấy batch hiện có: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    session_ids = [str(value) for value in manifest.get("session_ids", [])]
    if len(session_ids) != config.session_count:
        raise RuntimeError(
            f"session-count phải khớp manifest hiện có: {config.session_count} != {len(session_ids)}"
        )
    existing_session_rows = {row["session_id"]: row for row in _read_csv(output_dir / "sessions.csv")}
    existing_violation_rows = {
        row["event_id"]: row for row in _read_csv(output_dir / "violations.csv")
    }
    missing_dirs = [sid for sid in session_ids if not (config.sessions_root / sid).is_dir()]
    if missing_dirs:
        raise RuntimeError(f"Batch thiếu {len(missing_dirs)} thư mục session")

    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    staging_root = config.output_root / f".{config.batch_id}-model-evidence-staging-{stamp}"
    staging_root.mkdir(parents=True, exist_ok=False)
    staging_config = dataclasses.replace(config, sessions_root=staging_root)
    snapshot_payloads = {severity: snapshot_bytes(severity) for severity in ("LOW", "MEDIUM", "HIGH")}
    stats = GenerationStats(
        organization_id=str(manifest["organization"]["id"]),
        organization_name=str(manifest["organization"]["name"]),
        users=_read_csv(output_dir / "accounts.csv"),
        exams=_read_csv(output_dir / "exams.csv"),
        session_ids=session_ids.copy(),
        report_jobs=int(manifest.get("counts", {}).get("report_jobs", 0)),
        reports=list(manifest.get("reports", [])),
    )
    database_backup: Path | None = None
    output_backup: Path | None = None
    evidence_backup: Path | None = None

    Base.metadata.create_all(bind=engine)
    apply_additive_migrations(engine)
    try:
        with SessionLocal() as db:
            sessions_by_id = {
                row.id: row
                for row in db.query(models.ExamSession).filter(
                    models.ExamSession.id.in_(session_ids)
                ).all()
            }
            if len(sessions_by_id) != len(session_ids):
                raise RuntimeError("Database không có đủ session của batch")

            for index, session_id in enumerate(session_ids):
                source_dir = config.sessions_root / session_id
                source_meta = json.loads(
                    (source_dir / "session_meta.json").read_text(encoding="utf-8")
                )
                old_violations = _read_jsonl(source_dir / "violations.jsonl")
                old_browser_events = _read_jsonl(source_dir / "browser_events.jsonl")
                csv_row = existing_session_rows[session_id]
                exam_session = sessions_by_id[session_id]
                started_at = exam_session.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=UTC)
                ended_at = exam_session.ended_at
                if ended_at is not None and ended_at.tzinfo is None:
                    ended_at = ended_at.replace(tzinfo=UTC)
                duration_sec = float(source_meta.get("duration_sec") or csv_row["duration_sec"])
                rng = random.Random(config.seed * 1_000_003 + index + 9_173)
                _, violations, _, snapshots = make_session_evidence(
                    staging_config,
                    rng,
                    session_id,
                    exam_session.student_name,
                    exam_session.candidate_number or "",
                    exam_session.candidate_email,
                    exam_session.authentication_method,
                    exam_session.client_type,
                    exam_session.extension_version,
                    csv_row["risk_profile"],
                    started_at,
                    ended_at,
                    duration_sec,
                    snapshot_payloads,
                    desired_violation_count=len(old_violations),
                )
                jsonl_write(staging_root / session_id / "browser_events.jsonl", old_browser_events)
                validate_session_evidence(staging_root / session_id)
                risk_rows = _read_jsonl(staging_root / session_id / "risk_score_timeline.jsonl")
                peak_risk = max((float(row["risk_score"]) for row in risk_rows), default=0.0)
                last_risk = risk_rows[-1] if risk_rows else {
                    "risk_score": 0.0, "session_state": "SESSION_NORMAL"
                }
                exam_session.risk_score_current = float(last_risk["risk_score"])
                exam_session.session_state_current = str(last_risk["session_state"])
                exam_session.browser_event_count = len(old_browser_events)

                valid_event_ids = {row["event_id"] for row in violations}
                reviews = db.query(models.IncidentReview).filter_by(
                    exam_session_id=session_id
                ).all()
                for review in reviews:
                    if review.violation_event_id not in valid_event_ids:
                        db.delete(review)

                stats.browser_events += len(old_browser_events)
                stats.snapshots += snapshots
                stats.sessions.append({
                    "session_id": session_id,
                    "exam_id": exam_session.exam_id,
                    "exam_name": csv_row["exam_name"],
                    "student_name": exam_session.student_name,
                    "candidate_number": exam_session.candidate_number,
                    "candidate_email": exam_session.candidate_email,
                    "authentication_method": exam_session.authentication_method,
                    "client_type": exam_session.client_type,
                    "status": exam_session.status,
                    "risk_profile": csv_row["risk_profile"],
                    "risk_score_peak": round(peak_risk, 3),
                    "integrity_score": float(exam_session.integrity_score_current),
                    "violation_count": len(violations),
                    "browser_event_count": len(old_browser_events),
                    "started_at": iso(started_at),
                    "ended_at": iso(ended_at) if ended_at else None,
                    "duration_sec": duration_sec,
                })
                for violation in violations:
                    old_row = existing_violation_rows.get(violation["event_id"], {})
                    stats.violations.append({
                        "exam_id": exam_session.exam_id,
                        "session_id": session_id,
                        "event_id": violation["event_id"],
                        "student_name": exam_session.student_name,
                        "profile": csv_row["risk_profile"],
                        "video_time_sec": violation["video_time_sec"],
                        "violation_type": violation["primary_violation"],
                        "severity": violation["severity"],
                        "risk_score": violation["risk_score"],
                        "review_status": old_row.get("review_status", "new"),
                        "timestamp": violation["timestamp"],
                    })

            db.flush()
            stats.incident_reviews = db.query(models.IncidentReview).filter(
                models.IncidentReview.exam_session_id.in_(session_ids)
            ).count()

            database_backup = backup_sqlite_database(f"{config.batch_id}-pre-model-evidence")
            output_backup = config.output_root / f"{config.batch_id}-pre-model-evidence-{stamp}"
            shutil.copytree(output_dir, output_backup)
            evidence_backup = _backup_batch_evidence(config, session_ids, stamp)

            evidence_files = (
                "session_meta.json", "signals.jsonl", "state_transitions.jsonl",
                "violations.jsonl", "browser_events.jsonl", "risk_score_timeline.jsonl",
            )
            for session_id in session_ids:
                source_dir = staging_root / session_id
                target_dir = config.sessions_root / session_id
                for filename in evidence_files:
                    shutil.copy2(source_dir / filename, target_dir / filename)
                target_snapshots = target_dir / "snapshots"
                target_snapshots.mkdir(parents=True, exist_ok=True)
                for old_snapshot in target_snapshots.glob("evt_*"):
                    if old_snapshot.is_file():
                        old_snapshot.unlink()
                for new_snapshot in (source_dir / "snapshots").glob("evt_*"):
                    shutil.copy2(new_snapshot, target_snapshots / new_snapshot.name)

            validation = validate_dataset(db, config, stats)
            _rewrite_existing_batch_outputs(
                config, stats, manifest, database_backup, output_backup, evidence_backup
            )
            for report in manifest.get("reports", []):
                if report.get("format") in {"html", "pdf"}:
                    generate_report(
                        config.sessions_root / str(report["session_id"]),
                        fusion_config_path=ROOT / "config" / "fusion.yaml",
                        output_dir=config.sessions_root / str(report["session_id"]),
                        formats=[str(report["format"])],
                    )
            db.commit()
            counts = {
                **validation,
                "violations": len(stats.violations),
                "browser_events": stats.browser_events,
                "snapshots": stats.snapshots,
            }
    finally:
        if staging_root.is_dir() and staging_root.resolve().parent == config.output_root.resolve():
            shutil.rmtree(staging_root)

    assert output_backup is not None and evidence_backup is not None
    return counts, database_backup, output_backup, evidence_backup


def generate_sample_reports(
    db: Any,
    config: Config,
    stats: GenerationStats,
    requesters: list[models.User],
) -> None:
    if config.sample_reports <= 0 or not stats.sessions:
        return
    candidates = sorted(stats.sessions, key=lambda row: (row["violation_count"], row["risk_score_peak"]), reverse=True)
    selected = candidates[: min(config.sample_reports, len(candidates))]
    for index, row in enumerate(selected):
        session_dir = config.sessions_root / row["session_id"]
        try:
            paths = generate_report(
                session_dir,
                fusion_config_path=ROOT / "config" / "fusion.yaml",
                output_dir=session_dir,
                formats=list(config.report_formats),
            )
        except Exception as exc:  # Dataset remains useful even if optional PDF backend fails.
            stats.reports.append({"session_id": row["session_id"], "format": "error", "path": str(exc)})
            continue
        for fmt, path in paths.items():
            requester = requesters[index % len(requesters)]
            now = utc_now()
            db.add(models.ReportJob(
                id=stable_id(config.batch_id, "report-job", f"{row['session_id']}:{fmt}"),
                exam_session_id=row["session_id"],
                requested_by_user_id=requester.id,
                format=fmt,
                status="completed",
                output_path=str(path),
                created_at=now,
                started_at=now,
                completed_at=now,
                expires_at=now + timedelta(days=30),
            ))
            stats.report_jobs += 1
            stats.reports.append({"session_id": row["session_id"], "format": fmt, "path": str(path)})


def aggregate_rows(stats: GenerationStats) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    exam_lookup = {row["exam_id"]: row for row in stats.exams}
    exam_sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exam_violations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in stats.sessions:
        exam_sessions[row["exam_id"]].append(row)
    for row in stats.violations:
        exam_violations[row["exam_id"]].append(row)
    exam_summary: list[dict[str, Any]] = []
    for exam_id, exam in exam_lookup.items():
        sessions = exam_sessions[exam_id]
        violations = exam_violations[exam_id]
        profiles = Counter(row["risk_profile"] for row in sessions)
        exam_summary.append({
            "exam_id": exam_id,
            "exam_name": exam["exam_name"],
            "exam_status": exam["status"],
            "owner_email": exam["owner_email"],
            "session_count": len(sessions),
            "ended_sessions": sum(row["status"] == "ended" for row in sessions),
            "active_sessions": sum(row["status"] == "active" for row in sessions),
            "disconnected_sessions": sum(row["status"] == "disconnected" for row in sessions),
            "normal_profiles": profiles["normal"],
            "low_profiles": profiles["low"],
            "medium_profiles": profiles["medium"],
            "high_profiles": profiles["high"],
            "violation_count": len(violations),
            "high_violations": sum(row["severity"] == "HIGH" for row in violations),
            "confirmed_incidents": sum(row["review_status"] == "confirmed" for row in violations),
            "average_peak_risk": round(sum(row["risk_score_peak"] for row in sessions) / len(sessions), 2) if sessions else 0,
        })
    violation_counts = Counter((row["violation_type"], row["severity"], row["review_status"]) for row in stats.violations)
    violation_summary = [
        {"violation_type": key[0], "severity": key[1], "review_status": key[2], "count": count}
        for key, count in sorted(violation_counts.items())
    ]
    daily_counts: dict[str, dict[str, Any]] = {}
    for row in stats.sessions:
        day = row["started_at"][:10]
        item = daily_counts.setdefault(day, {"date": day, "sessions": 0, "violations": 0, "browser_events": 0, "high_risk_sessions": 0})
        item["sessions"] += 1
        item["violations"] += row["violation_count"]
        item["browser_events"] += row["browser_event_count"]
        item["high_risk_sessions"] += row["risk_profile"] == "high"
    return exam_summary, violation_summary, [daily_counts[key] for key in sorted(daily_counts)]


def write_outputs(config: Config, stats: GenerationStats, backup_path: Path | None) -> None:
    output_dir = config.output_root / config.batch_id
    if output_dir.exists():
        raise RuntimeError(f"Thư mục output đã tồn tại: {output_dir}")
    output_dir.mkdir(parents=True)
    csv_write(
        output_dir / "accounts.csv",
        ("email", "password", "display_name", "organization_role", "exam_role", "purpose"),
        stats.users,
    )
    csv_write(
        output_dir / "exams.csv",
        ("exam_id", "exam_name", "status", "owner_email", "candidate_auth_mode", "scheduled_start_at", "scheduled_end_at", "assignments"),
        stats.exams,
    )
    csv_write(
        output_dir / "sessions.csv",
        ("session_id", "exam_id", "exam_name", "student_name", "candidate_number", "candidate_email", "authentication_method", "client_type", "status", "risk_profile", "risk_score_peak", "integrity_score", "violation_count", "browser_event_count", "started_at", "ended_at", "duration_sec"),
        stats.sessions,
    )
    csv_write(
        output_dir / "violations.csv",
        ("exam_id", "session_id", "event_id", "student_name", "profile", "video_time_sec", "violation_type", "severity", "risk_score", "review_status", "timestamp"),
        stats.violations,
    )
    exam_summary, violation_summary, daily_summary = aggregate_rows(stats)
    csv_write(output_dir / "exam_summary.csv", tuple(exam_summary[0]) if exam_summary else ("exam_id",), exam_summary)
    csv_write(output_dir / "violation_summary.csv", ("violation_type", "severity", "review_status", "count"), violation_summary)
    csv_write(output_dir / "daily_summary.csv", ("date", "sessions", "violations", "browser_events", "high_risk_sessions"), daily_summary)
    csv_write(
        output_dir / "role_matrix.csv",
        ("role", "scope", "capabilities"),
        (
            {"role": "org_admin", "scope": "organization", "capabilities": "members, policy, audit; không tự động truy cập kỳ thi"},
            {"role": "owner", "scope": "assigned exam", "capabilities": "manage, assign, monitor, evidence, review, export"},
            {"role": "manager", "scope": "assigned exam", "capabilities": "manage, assign, monitor, evidence, review, export"},
            {"role": "proctor", "scope": "assigned exam", "capabilities": "monitor, end session, evidence, review, export"},
        ),
    )
    manifest = {
        "batch_id": config.batch_id,
        "generated_at": iso(utc_now()),
        "database_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
        "database_backup": str(backup_path) if backup_path else None,
        "organization": {"id": stats.organization_id, "name": stats.organization_name},
        "configuration": {
            "target_email": config.target_email,
            "exam_count": config.exam_count,
            "session_count": config.session_count,
            "days": config.days,
            "seed": config.seed,
            "org_admins": config.org_admins,
            "managers": config.managers,
            "proctors": config.proctors,
            "snapshot_rate": config.snapshot_rate,
            "sample_reports": config.sample_reports,
            "report_formats": config.report_formats,
        },
        "counts": {
            "users": len(stats.users),
            "exams": len(stats.exams),
            "sessions": len(stats.sessions),
            "violations": len(stats.violations),
            "browser_events": stats.browser_events,
            "incident_reviews": stats.incident_reviews,
            "snapshots": stats.snapshots,
            "report_jobs": stats.report_jobs,
        },
        "session_ids": stats.session_ids,
        "reports": stats.reports,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "README.md").write_text(
        f"""# Bộ dữ liệu báo cáo `{config.batch_id}`

- Tổ chức: **{stats.organization_name}**
- Tài khoản: **{len(stats.users)}** (`accounts.csv`)
- Kỳ thi: **{len(stats.exams)}**
- Phiên thi: **{len(stats.sessions)}**
- Vi phạm CV: **{len(stats.violations)}**
- Sự kiện trình duyệt: **{stats.browser_events}**
- Incident review đã lưu: **{stats.incident_reviews}**

Các file `exam_summary.csv`, `daily_summary.csv` và `violation_summary.csv` có
thể nhập trực tiếp vào Excel/Google Sheets để dựng bảng và biểu đồ báo cáo.
`sessions.csv` và `violations.csv` chứa dữ liệu chi tiết. Tất cả ứng viên,
email, snapshot và sự kiện trong batch đều là dữ liệu tổng hợp.

Tài khoản `org_admin` quản trị tenant nhưng không tự động xem kỳ thi. Dùng tài
khoản `manager` hoặc `proctor` trong `accounts.csv` để kiểm tra dashboard kỳ
thi theo đúng phạm vi phân công.
""",
        encoding="utf-8",
    )


def validate_dataset(db: Any, config: Config, stats: GenerationStats) -> dict[str, int]:
    user_ids = [stable_id(config.batch_id, "user", f"{group}:{index + 1}") for group, count in (
        ("org_admin", config.org_admins), ("manager", config.managers), ("proctor", config.proctors)
    ) for index in range(count)]
    exam_ids = [stable_id(config.batch_id, "exam", index) for index in range(config.exam_count)]
    counts = {
        "users": db.query(models.User).filter(models.User.id.in_(user_ids)).count(),
        "memberships": db.query(models.OrganizationMembership).filter(models.OrganizationMembership.user_id.in_(user_ids)).count(),
        "exams": db.query(models.Exam).filter(models.Exam.id.in_(exam_ids)).count(),
        "assignments": db.query(models.ExamAssignment).filter(models.ExamAssignment.exam_id.in_(exam_ids)).count(),
        "sessions": db.query(models.ExamSession).filter(models.ExamSession.id.in_(stats.session_ids)).count(),
        "reviews": db.query(models.IncidentReview).filter(models.IncidentReview.exam_session_id.in_(stats.session_ids)).count(),
    }
    expected = {
        "users": len(user_ids), "memberships": len(user_ids), "exams": config.exam_count,
        "sessions": config.session_count, "reviews": stats.incident_reviews,
    }
    for name, expected_count in expected.items():
        if counts[name] != expected_count:
            raise RuntimeError(f"Kiểm tra {name} thất bại: {counts[name]} != {expected_count}")
    if counts["assignments"] < config.exam_count * 3:
        raise RuntimeError("Mỗi kỳ thi phải có ít nhất owner, manager và proctor")
    required = {
        "session_meta.json", "signals.jsonl", "state_transitions.jsonl",
        "violations.jsonl", "browser_events.jsonl", "risk_score_timeline.jsonl",
    }
    parsed_violations = 0
    for session_id in stats.session_ids:
        session_dir = config.sessions_root / session_id
        missing = [name for name in required if not (session_dir / name).is_file()]
        if missing:
            raise RuntimeError(f"Phiên {session_id} thiếu file: {missing}")
        meta = json.loads((session_dir / "session_meta.json").read_text(encoding="utf-8"))
        if meta.get("session_id") != session_id:
            raise RuntimeError(f"Metadata phiên không hợp lệ: {session_id}")
        evidence_counts = validate_session_evidence(session_dir)
        parsed_violations += evidence_counts["violations"]
        _read_jsonl(session_dir / "browser_events.jsonl")
    if parsed_violations != len(stats.violations):
        raise RuntimeError(f"Số violation JSONL sai: {parsed_violations} != {len(stats.violations)}")
    return counts


def backup_sqlite_database(batch_id: str) -> Path | None:
    if not DATABASE_URL.startswith("sqlite"):
        return None
    database = engine.url.database
    if not database or database == ":memory:":
        return None
    source = Path(database)
    if not source.is_absolute():
        source = (ROOT / source).resolve()
    if not source.is_file():
        return None
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    destination = source.with_name(f"{source.name}-seed-backup-{batch_id}-{stamp}")
    shutil.copy2(source, destination)
    return destination


def remove_partial_session_dirs(config: Config, session_ids: Sequence[str]) -> None:
    root = config.sessions_root.resolve()
    for session_id in session_ids:
        target = (config.sessions_root / session_id).resolve()
        if target.parent == root and target.name == session_id and target.is_dir():
            shutil.rmtree(target)


def generate(config: Config) -> tuple[GenerationStats, Path | None, dict[str, int]]:
    config.sessions_root.mkdir(parents=True, exist_ok=True)
    if (config.output_root / config.batch_id).exists():
        raise RuntimeError(f"Batch output đã tồn tại: {config.output_root / config.batch_id}")
    Base.metadata.create_all(bind=engine)
    apply_additive_migrations(engine)
    backup_path = backup_sqlite_database(config.batch_id)
    stats = GenerationStats()
    now = utc_now()
    with SessionLocal() as db:
        try:
            target_user = db.query(models.User).filter(models.User.email == config.target_email).first()
            if target_user is None:
                raise RuntimeError(f"Không tìm thấy tài khoản mục tiêu: {config.target_email}")
            membership = db.query(models.OrganizationMembership).filter_by(
                user_id=target_user.id, org_id=target_user.org_id, status="active"
            ).first()
            if membership is None:
                raise RuntimeError("Tài khoản mục tiêu không có membership hoạt động")
            org = db.get(models.Organization, membership.org_id)
            if org is None:
                raise RuntimeError("Không tìm thấy tổ chức của tài khoản mục tiêu")
            stats.organization_id = org.id
            stats.organization_name = org.name
            shared_hash = hash_password(config.password)
            _, managers, proctors, stats.users = create_users(
                db, config, org, target_user.id, shared_hash
            )
            exams, stats.exams = create_exams_and_assignments(
                db, config, org, managers, proctors, now
            )
            identities = create_candidate_identities(db, config, now)
            create_sessions(db, config, org, exams, identities, managers, proctors, now, stats)
            db.flush()
            generate_sample_reports(db, config, stats, managers + proctors)
            db.flush()
            validation = validate_dataset(db, config, stats)
            write_outputs(config, stats, backup_path)
            db.commit()
            return stats, backup_path, validation
        except Exception:
            db.rollback()
            remove_partial_session_dirs(config, stats.session_ids)
            output_dir = config.output_root / config.batch_id
            if output_dir.is_dir() and output_dir.resolve().parent == config.output_root.resolve():
                shutil.rmtree(output_dir)
            raise


def dry_run(config: Config) -> None:
    with SessionLocal() as db:
        user = db.query(models.User).filter(models.User.email == config.target_email).first()
        if user is None:
            raise RuntimeError(f"Không tìm thấy tài khoản mục tiêu: {config.target_email}")
        org = db.get(models.Organization, user.org_id)
        if org is None:
            raise RuntimeError("Không tìm thấy tổ chức của tài khoản mục tiêu")
        print(f"[DRY-RUN] Tổ chức: {org.name} ({org.id})")
    estimated_violations = int(config.session_count * sum(
        weight * ((VIOLATION_RANGES[name][0] + VIOLATION_RANGES[name][1]) / 2)
        for name, weight in PROFILE_WEIGHTS
    ))
    print(f"[DRY-RUN] {config.org_admins} org_admin, {config.managers} manager, {config.proctors} proctor")
    print(f"[DRY-RUN] {config.exam_count} kỳ thi, {config.session_count} phiên, ~{estimated_violations} violations")
    print(f"[DRY-RUN] Sessions: {config.sessions_root}")
    print(f"[DRY-RUN] Báo cáo tổng hợp: {config.output_root / config.batch_id}")


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="Sinh dữ liệu lớn cho dashboard/báo cáo DATT")
    parser.add_argument("--batch-id", type=sanitize_batch_id, default="report-2026")
    parser.add_argument("--target-email", default="test@gmail.com", help="Tài khoản xác định tổ chức đích")
    parser.add_argument("--exam-count", type=int, default=10)
    parser.add_argument("--session-count", type=int, default=1000)
    parser.add_argument("--days", type=int, default=180, help="Khoảng lịch sử dữ liệu")
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument("--org-admins", type=int, default=2)
    parser.add_argument("--managers", type=int, default=3)
    parser.add_argument("--proctors", type=int, default=4)
    parser.add_argument("--snapshot-rate", type=float, default=0.05)
    parser.add_argument("--sample-reports", type=int, default=3)
    parser.add_argument("--report-formats", default="html,pdf")
    parser.add_argument("--sessions-root", type=Path, default=Path(os.environ.get("SESSIONS_ROOT", ROOT / "sessions")))
    parser.add_argument("--output-root", type=Path, default=ROOT / "generated_reports")
    parser.add_argument("--staff-domain", default="phenikaa.edu.vn")
    parser.add_argument("--student-domain", default="st.phenikaa.edu.vn")
    parser.add_argument("--exam-domain", default="lms.phenikaa.edu.vn")
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Cập nhật tên/email/URL/audit/evidence của batch hiện có mà không đổi ID và số lượng",
    )
    parser.add_argument(
        "--regenerate-model-evidence",
        action="store_true",
        help="Sinh lại evidence của batch hiện có bằng RiskFusionEngine thực tế",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.refresh_existing and args.regenerate_model_evidence:
        parser.error("chỉ chọn một trong --refresh-existing và --regenerate-model-evidence")
    if args.exam_count < 3 or args.session_count < 1 or args.days < 1:
        parser.error("exam-count >= 3, session-count >= 1 và days >= 1")
    if args.org_admins < 1 or args.managers < 2 or args.proctors < 1:
        parser.error("cần ít nhất 1 org_admin, 2 manager và 1 proctor")
    if not 0.0 <= args.snapshot_rate <= 1.0:
        parser.error("snapshot-rate phải nằm trong [0, 1]")
    if args.sample_reports < 0:
        parser.error("sample-reports không được âm")
    formats = tuple(item.strip().lower() for item in args.report_formats.split(",") if item.strip())
    if not formats or set(formats) - {"html", "pdf"}:
        parser.error("report-formats chỉ nhận html,pdf")
    domain_pattern = re.compile(r"(?=^.{3,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
    for label, value in (
        ("staff-domain", args.staff_domain),
        ("student-domain", args.student_domain),
        ("exam-domain", args.exam_domain),
    ):
        if not domain_pattern.fullmatch(value.strip().lower()):
            parser.error(f"{label} không hợp lệ")
    password = os.environ.get("REPORT_DATA_PASSWORD") or f"Demo-{secrets.token_urlsafe(12)}"
    if len(password) < 12 or len(password.encode("utf-8")) > 72:
        parser.error("REPORT_DATA_PASSWORD phải dài 12-72 byte UTF-8")
    return Config(
        batch_id=args.batch_id,
        target_email=args.target_email.strip().casefold(),
        exam_count=args.exam_count,
        session_count=args.session_count,
        days=args.days,
        seed=args.seed,
        org_admins=args.org_admins,
        managers=args.managers,
        proctors=args.proctors,
        snapshot_rate=args.snapshot_rate,
        sample_reports=args.sample_reports,
        report_formats=formats,
        sessions_root=args.sessions_root.resolve(),
        output_root=args.output_root.resolve(),
        password=password,
        dry_run=args.dry_run,
        staff_domain=args.staff_domain.strip().lower(),
        student_domain=args.student_domain.strip().lower(),
        exam_domain=args.exam_domain.strip().lower(),
        refresh_existing=args.refresh_existing,
        regenerate_model_evidence=args.regenerate_model_evidence,
    )


def main() -> None:
    config = parse_args()
    if config.dry_run:
        dry_run(config)
        return
    if config.refresh_existing:
        counts, database_backup, output_backup = refresh_existing_dataset(config)
        print(f"Đã cập nhật dữ liệu hiển thị của batch: {config.batch_id}")
        print(f"Kết quả: {counts}")
        if database_backup:
            print(f"Database backup: {database_backup}")
        print(f"Output backup: {output_backup}")
        return
    if config.regenerate_model_evidence:
        counts, database_backup, output_backup, evidence_backup = regenerate_existing_model_evidence(config)
        print(f"Đã sinh lại model evidence của batch: {config.batch_id}")
        print(f"Kết quả: {counts}")
        if database_backup:
            print(f"Database backup: {database_backup}")
        print(f"Output backup: {output_backup}")
        print(f"Evidence backup: {evidence_backup}")
        return
    stats, backup_path, validation = generate(config)
    print(f"Hoàn tất batch: {config.batch_id}")
    print(f"Tổ chức: {stats.organization_name}")
    print(f"Tài khoản: {len(stats.users)}; kỳ thi: {len(stats.exams)}; phiên: {len(stats.sessions)}")
    print(f"Violations: {len(stats.violations)}; browser events: {stats.browser_events}; reviews: {stats.incident_reviews}")
    print(f"Snapshots: {stats.snapshots}; report jobs: {stats.report_jobs}")
    print(f"Validation: {validation}")
    if backup_path:
        print(f"Database backup: {backup_path}")
    print(f"Tài khoản và CSV báo cáo: {config.output_root / config.batch_id}")


if __name__ == "__main__":
    main()
