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

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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
    slug: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    settings_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    quota_concurrent_sessions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    users: Mapped[List["User"]] = relationship(back_populates="organization")
    exams: Mapped[List["Exam"]] = relationship(back_populates="organization")
    memberships: Mapped[List["OrganizationMembership"]] = relationship(
        back_populates="organization",
    )


class User(Base):
    """Chi admin/proctor; CandidateIdentity khong phai User platform."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    google_subject: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True, index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "admin" | "proctor"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mfa_recovery_codes_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    organization: Mapped["Organization"] = relationship(back_populates="users")
    memberships: Mapped[List["OrganizationMembership"]] = relationship(
        back_populates="user",
        foreign_keys="OrganizationMembership.user_id",
    )


class WebAuthChallenge(Base):
    """Short-lived, server-side state for MFA and Google registration."""

    __tablename__ = "web_auth_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    google_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    google_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    google_display_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    google_avatar_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class WebOAuthTransaction(Base):
    """One-time OAuth state/PKCE transaction for the server-rendered web UI."""

    __tablename__ = "web_oauth_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    flow: Mapped[str] = mapped_column(String(20), nullable=False)
    pkce_verifier: Mapped[str] = mapped_column(String(255), nullable=False)
    oidc_nonce: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


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
    owner_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True,
    )
    scheduled_start_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    scheduled_end_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    organization: Mapped["Organization"] = relationship(back_populates="exams")
    sessions: Mapped[List["ExamSession"]] = relationship(back_populates="exam")
    assignments: Mapped[List["ExamAssignment"]] = relationship(back_populates="exam")


class OrganizationMembership(Base):
    """Vai tro cua User trong mot tenant.

    `User.org_id`/`User.role` van duoc giu trong giai doan chuyen doi de cac
    client cu tiep tuc hoat dong. Authorization v2 se doc bang nay.
    """

    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),
        Index("ix_membership_org_role_status", "org_id", "role", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True,
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)  # org_admin | exam_manager
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    invited_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship(
        back_populates="memberships",
        foreign_keys=[user_id],
    )
    organization: Mapped["Organization"] = relationship(back_populates="memberships")


class SystemRole(Base):
    __tablename__ = "system_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_system_role_user_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="system_admin")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    granted_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ExamAssignment(Base):
    __tablename__ = "exam_assignments"
    __table_args__ = (
        UniqueConstraint("exam_id", "user_id", name="uq_exam_assignment_exam_user"),
        Index("ix_exam_assignment_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    assignment_role: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )  # owner | manager | proctor
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    assigned_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    exam: Mapped["Exam"] = relationship(back_populates="assignments")


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        Index("ix_invitation_org_email_status", "org_id", "email", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    invited_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    accepted_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_org_created", "org_id", "created_at"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    actor_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True,
    )
    actor_role: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    org_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True,
    )
    exam_id: Mapped[Optional[str]] = mapped_column(ForeignKey("exams.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    before_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class AccessGrant(Base):
    __tablename__ = "access_grants"
    __table_args__ = (
        Index("ix_access_grant_org_status_expiry", "org_id", "status", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    requester_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True,
    )
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True,
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), nullable=False, default="evidence.read")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approved_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


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


class IncidentReview(Base):
    """Human review layered on top of immutable violation JSONL events."""

    __tablename__ = "incident_reviews"
    __table_args__ = (
        UniqueConstraint(
            "exam_session_id",
            "violation_event_id",
            name="uq_incident_review_session_event",
        ),
        Index("ix_incident_review_status_updated", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    exam_session_id: Mapped[str] = mapped_column(
        ForeignKey("exam_sessions.id"), nullable=False, index=True,
    )
    violation_event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportJob(Base):
    __tablename__ = "report_jobs"
    __table_args__ = (
        Index("ix_report_job_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    exam_session_id: Mapped[str] = mapped_column(
        ForeignKey("exam_sessions.id"), nullable=False, index=True,
    )
    requested_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True,
    )
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    output_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


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
