"""Cau hinh cap ung dung (Tuan 13) - doc tu chinh `config/fusion.yaml`
(khong tach file rieng, xem quyet dinh o docs/KE_HOACH_CHI_TIET_TUAN12.md
muc 1 va ghi chu trong chinh file YAML).

Dung nap (tolerant) theo dung phong cach src/fusion/config.py: thieu ca 4
muc moi (`camera`/`paths`/`enrollment`/`report`/`backend`) van tra ve dung
gia tri MAC DINH da tung hardcode trong main.py truoc Tuan 13 - dam bao hanh
vi khong doi neu ai chua cap nhat YAML.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union

import yaml


@dataclass(frozen=True)
class CameraConfig:
    source: int = 0
    window_name: str = "Demo - 7 signal extractor"


@dataclass(frozen=True)
class EnrollmentConfig:
    num_frames: int = 5
    max_attempts: int = 5
    require_liveness: bool = False
    liveness_timeout_sec: float = 20.0
    liveness_min_open_frames: int = 2
    liveness_min_closed_frames: int = 2


@dataclass(frozen=True)
class ReportConfig:
    auto_generate: bool = True
    auto_open: bool = True
    formats: List[str] = field(default_factory=lambda: ["html", "pdf"])


@dataclass(frozen=True)
class BackendConfig:
    """Ket noi backend (Tuan 12 moi, xem docs/KE_HOACH_PLATFORM.md).
    `enabled=False` mac dinh - giu nguyen luong 1-may cu (khong join-code,
    khong can docker compose dang chay)."""

    enabled: bool = False
    base_url: str = "http://localhost:8000"
    ws_url: str = "ws://localhost:8000"
    telemetry_interval_sec: float = 1.0


@dataclass(frozen=True)
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    sessions_dir: str = "sessions"
    enrollment: EnrollmentConfig = field(default_factory=EnrollmentConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)

    @classmethod
    def from_yaml(cls, config_path: Union[str, Path] = "config/fusion.yaml") -> "AppConfig":
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        camera_cfg = raw.get("camera") or {}
        paths_cfg = raw.get("paths") or {}
        enrollment_cfg = raw.get("enrollment") or {}
        report_cfg = raw.get("report") or {}
        backend_cfg = raw.get("backend") or {}

        d = cls()
        formats = report_cfg.get("formats", d.report.formats)
        if not isinstance(formats, list) or not formats or any(fmt not in {"html", "pdf"} for fmt in formats):
            raise ValueError("report.formats phai la danh sach khong rong gom html/pdf")
        telemetry_interval_sec = float(
            backend_cfg.get("telemetry_interval_sec", d.backend.telemetry_interval_sec),
        )
        if telemetry_interval_sec <= 0:
            raise ValueError("backend.telemetry_interval_sec phai > 0")
        return cls(
            camera=CameraConfig(
                source=camera_cfg.get("source", d.camera.source),
                window_name=camera_cfg.get("window_name", d.camera.window_name),
            ),
            sessions_dir=paths_cfg.get("sessions_dir", d.sessions_dir),
            enrollment=EnrollmentConfig(
                num_frames=enrollment_cfg.get("num_frames", d.enrollment.num_frames),
                max_attempts=enrollment_cfg.get("max_attempts", d.enrollment.max_attempts),
                require_liveness=enrollment_cfg.get("require_liveness", d.enrollment.require_liveness),
                liveness_timeout_sec=enrollment_cfg.get(
                    "liveness_timeout_sec", d.enrollment.liveness_timeout_sec,
                ),
                liveness_min_open_frames=enrollment_cfg.get(
                    "liveness_min_open_frames", d.enrollment.liveness_min_open_frames,
                ),
                liveness_min_closed_frames=enrollment_cfg.get(
                    "liveness_min_closed_frames", d.enrollment.liveness_min_closed_frames,
                ),
            ),
            report=ReportConfig(
                auto_generate=report_cfg.get("auto_generate", d.report.auto_generate),
                auto_open=report_cfg.get("auto_open", d.report.auto_open),
                formats=list(dict.fromkeys(formats)),
            ),
            backend=BackendConfig(
                enabled=backend_cfg.get("enabled", d.backend.enabled),
                base_url=backend_cfg.get("base_url", d.backend.base_url),
                ws_url=backend_cfg.get("ws_url", d.backend.ws_url),
                telemetry_interval_sec=telemetry_interval_sec,
            ),
        )
