"""SQLAlchemy models cho lop platform - xem docs/KE_HOACH_PLATFORM.md.

Chi luu con tro/trang thai (khong luu noi dung SignalResult/ViolationEvent -
cac thu do van nam trong file sessions/<id>/*.jsonl dung schema cu, xem
backend/session_materializer.py) - de src/reporting/ tai dung nguyen khong
doi gi.

Thi sinh manual khong co row User. Che do Google co CandidateIdentity rieng,
tach khoi User admin/proctor va chi luu claim OIDC toi thieu da xac minh.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _default_join_code_expiry() -> datetime:
    return _now() + timedelta(hours=24)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    users: Mapped[List["User"]] = relationship(back_populates="organization")
    exams: Mapped[List["Exam"]] = relationship(back_populates="organization")


class User(Base):
    """Chi admin/proctor; CandidateIdentity khong phai User platform."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "admin" | "proctor"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    organization: Mapped["Organization"] = relationship(back_populates="users")


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    join_code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    join_code_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_default_join_code_expiry,
    )
    candidate_auth_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual",
    )  # manual | google
    exam_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    require_extension: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    min_extension_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1.0.0",
    )
    require_fullscreen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_camera: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_microphone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_screen_share: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    block_clipboard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_focus_loss_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    google_allowed_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    organization: Mapped["Organization"] = relationship(back_populates="exams")
    sessions: Mapped[List["ExamSession"]] = relationship(back_populates="exam")


class ExamSession(Base):
    """1 phien giam sat cua 1 hoc sinh. `id` dung luon lam ten thu muc
    `sessions/<id>/` (khong them field session_uuid rieng trung lap voi id).

    `risk_score_current`/`session_state_current` la ban sao "moi nhat" duoc
    cap nhat moi lan nhan message qua WebSocket (backend/routers/ws.py) - de
    dashboard load danh sach phien ban dau (GET /exams/{id}/sessions) co ngay
    trang thai hien tai ma khong can doc lai file jsonl.
    """

    __tablename__ = "exam_sessions"
    __table_args__ = (
        UniqueConstraint("exam_id", "candidate_number", name="uq_exam_candidate_number"),
        UniqueConstraint("exam_id", "candidate_identity_id", name="uq_exam_candidate_identity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False)
    student_name: Mapped[str] = mapped_column(String(200), nullable=False)
    candidate_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    candidate_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    candidate_identity_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("candidate_identities.id"), nullable=True,
    )
    authentication_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual",
    )
    client_type: Mapped[str] = mapped_column(String(32), nullable=False, default="desktop_cv")
    extension_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    browser_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    device_id_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
    )  # pending|active|disconnected|ended
    risk_score_current: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    session_state_current: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SESSION_NORMAL"
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    disconnect_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    integrity_score_current: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    integrity_status_current: Mapped[str] = mapped_column(
        String(20), nullable=False, default="healthy",
    )
    browser_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    exam: Mapped["Exam"] = relationship(back_populates="sessions")
    candidate_identity: Mapped[Optional["CandidateIdentity"]] = relationship(
        back_populates="sessions",
    )


class CandidateIdentity(Base):
    """Danh tinh Google da duoc backend xac minh.

    Chi luu cac claim OIDC toi thieu. Access token/refresh token cua Google
    khong bao gio duoc luu trong database nay.
    """

    __tablename__ = "candidate_identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="google")
    provider_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    hosted_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    devices: Mapped[List["CandidateDevice"]] = relationship(back_populates="candidate_identity")
    sessions: Mapped[List["ExamSession"]] = relationship(back_populates="candidate_identity")


class CandidateDevice(Base):
    """Opaque token do he thong cap cho mot cai dat extension.

    Database chi giu SHA-256 cua token va device id; raw token chi tra ve
    mot lan cho extension va co the bi thu hoi.
    """

    __tablename__ = "candidate_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    candidate_identity_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_identities.id"), nullable=False, index=True,
    )
    device_id_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    candidate_identity: Mapped["CandidateIdentity"] = relationship(back_populates="devices")


class CandidateOAuthTransaction(Base):
    """State/PKCE va grant mot-lan cho luong Google OAuth cua extension."""

    __tablename__ = "candidate_oauth_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    extension_redirect_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    pkce_verifier: Mapped[str] = mapped_column(String(255), nullable=False)
    oidc_nonce: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    candidate_identity_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("candidate_identities.id"), nullable=True,
    )
    grant_hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    grant_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    grant_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
