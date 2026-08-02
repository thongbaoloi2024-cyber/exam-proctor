"""AppState - state machine cua ung dung (thiet ke o docs/KE_HOACH_CHI_TIET_TUAN12.md,
xay o Tuan 13). IDLE gom ca man hinh nhap ten + join-code truoc khi bam Start
(khong tach state rieng - goi REST join la 1 loi goi chan ngan, cung phong
cach voi _run_enrollment cu)."""
from __future__ import annotations

from enum import Enum


class AppState(Enum):
    IDLE = "IDLE"
    ENROLLMENT = "ENROLLMENT"
    MONITORING = "MONITORING"
    GENERATING_REPORT = "GENERATING_REPORT"
    ENDED = "ENDED"
