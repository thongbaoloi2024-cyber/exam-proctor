"""Exam lifecycle, proctor-controlled candidate auth policy, and joining."""
from __future__ import annotations

import os
import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..auth import create_session_token, get_current_user
from ..authorization import (
    Permission,
    active_membership,
    active_system_role,
    authorize_exam,
    exam_access_for_user,
    require_permission,
    scoped_exam_query,
)
from ..audit import record_audit
from ..candidate_tokens import (
    bearer_token_from_request,
    hash_device_id,
    resolve_candidate_token,
)
from ..db import get_db
from ..policies import (
    EXAM_POLICY_FIELDS,
    OrganizationPolicy,
    exam_policy_values,
    get_effective_organization_policy,
    resolve_exam_policy,
)
from ..rate_limit import JOIN_CODE_LIMIT_PER_MINUTE, PUBLIC_IP_LIMIT_PER_MINUTE, enforce_rate_limit
from .candidate_auth import google_oauth_configured

router = APIRouter(prefix="/exams", tags=["exams"])

_JOIN_CODE_ALPHABET = string.ascii_uppercase + string.digits
_JOIN_CODE_LENGTH = 6
_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")
_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")
_ALLOWED_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"scheduled", "open", "archived"}),
    "scheduled": frozenset({"draft", "open", "closed"}),
    "open": frozenset({"closed"}),
    "closed": frozenset({"open", "archived"}),
    "archived": frozenset(),
}
_LIVE_SESSION_STATUSES = frozenset({"pending", "active", "disconnected"})


def _generate_join_code(db: Session) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(_JOIN_CODE_ALPHABET) for _ in range(_JOIN_CODE_LENGTH))
        if db.query(models.Exam).filter(models.Exam.join_code == code).first() is None:
            return code
    raise RuntimeError("Khong sinh duoc join_code duy nhat sau 20 lan thu")


def _active_exam_session_count(db: Session, exam_id: str) -> int:
    return db.query(models.ExamSession).filter(
        models.ExamSession.exam_id == exam_id,
        models.ExamSession.status.in_(_LIVE_SESSION_STATUSES),
    ).count()


def _normalize_human_text(value: Optional[str], *, label: str) -> Optional[str]:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    if not normalized:
        return None
    if any(ord(char) < 32 for char in normalized):
        raise ValueError(f"{label} chua ky tu dieu khien")
    return normalized


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = _SEMVER_RE.fullmatch(value)
    if match is None:
        raise ValueError("Phien ban extension phai co dang MAJOR.MINOR.PATCH")
    return tuple(int(match.group(i)) for i in (1, 2, 3))


def _validate_exam_url(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        raise ValueError("URL bai thi phai la dia chi HTTP(S) hop le")
    production = os.environ.get("APP_ENV", "development").strip().lower() == "production"
    if production and parts.scheme != "https":
        raise ValueError("URL bai thi phai dung HTTPS trong production")
    return value


class CreateExamRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    initial_status: Literal["draft", "scheduled", "open"] = "open"
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    join_code_ttl_minutes: int = Field(default=24 * 60, ge=5, le=7 * 24 * 60)
    candidate_auth_mode: Literal["manual", "google"] = "manual"
    exam_url: Optional[str] = Field(default=None, max_length=2048)
    require_extension: bool = False
    min_extension_version: str = Field(default="1.0.0", min_length=5, max_length=32)
    require_fullscreen: bool = True
    require_camera: bool = True
    require_microphone: bool = False
    require_screen_share: bool = False
    block_clipboard: bool = True
    max_focus_loss_seconds: float = Field(default=5.0, ge=0.0, le=300.0)
    google_allowed_domain: Optional[str] = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = _normalize_human_text(value, label="Ten ky thi") or ""
        if not value:
            raise ValueError("Ten ky thi khong duoc de trong")
        return value

    @field_validator("exam_url")
    @classmethod
    def valid_exam_url(cls, value: Optional[str]) -> Optional[str]:
        return _validate_exam_url(value)

    @field_validator("min_extension_version")
    @classmethod
    def valid_min_version(cls, value: str) -> str:
        _version_tuple(value)
        return value

    @field_validator("google_allowed_domain")
    @classmethod
    def valid_google_domain(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        value = value.strip().casefold()
        if _DOMAIN_RE.fullmatch(value) is None:
            raise ValueError("Google Workspace domain khong hop le")
        return value

    @model_validator(mode="after")
    def coherent_policy(self) -> "CreateExamRequest":
        if (self.scheduled_start_at is None) != (self.scheduled_end_at is None):
            raise ValueError("Phai dat ca thoi gian bat dau va ket thuc")
        if self.scheduled_start_at and self.scheduled_end_at:
            if _as_utc(self.scheduled_end_at) <= _as_utc(self.scheduled_start_at):
                raise ValueError("Thoi gian ket thuc phai sau thoi gian bat dau")
        if self.initial_status == "scheduled" and self.scheduled_start_at is None:
            raise ValueError("Ky thi scheduled phai co lich bat dau/ket thuc")
        return self


class ExamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    join_code: Optional[str]
    status: str
    join_code_expires_at: datetime
    candidate_auth_mode: str
    exam_url: Optional[str]
    require_extension: bool
    min_extension_version: str
    require_fullscreen: bool
    require_camera: bool
    require_microphone: bool
    require_screen_share: bool
    block_clipboard: bool
    max_focus_loss_seconds: float
    google_allowed_domain: Optional[str]
    owner_user_id: Optional[str]
    scheduled_start_at: Optional[datetime]
    scheduled_end_at: Optional[datetime]
    archived_at: Optional[datetime]
    version: int
    created_at: datetime
    updated_at: datetime
    assignment_role: Optional[str] = None
    allowed_actions: list[str] = Field(default_factory=list)
    allowed_transitions: list[str] = Field(default_factory=list)
    is_pinned: bool = False
    pinned_at: datetime | None = None


class UpdateExamPinRequest(BaseModel):
    is_pinned: bool


class PinnedExamResponse(BaseModel):
    id: str
    name: str
    status: str
    assignment_role: str
    pinned_at: datetime


class ExamWorkspaceItem(BaseModel):
    id: str
    name: str
    status: str
    assignment_role: str
    scheduled_start_at: datetime | None
    scheduled_end_at: datetime | None
    join_code_expires_at: datetime
    active_sessions: int
    disconnected_sessions: int
    alert_sessions: int
    open_reviews: int
    allowed_actions: list[str]
    attention: list[str]


class ExamWorkspaceOverviewResponse(BaseModel):
    assigned_exams_total: int
    managed_exams: int
    proctored_exams: int
    open_exams: int
    scheduled_exams: int
    active_sessions: int
    disconnected_sessions: int
    alert_sessions: int
    open_reviews: int
    exam_status: dict[str, int]
    assignment_roles: dict[str, int]
    items: list[ExamWorkspaceItem]


def _exam_response_for_user(
    db: Session,
    user: models.User,
    exam: models.Exam,
) -> ExamResponse:
    response = ExamResponse.model_validate(exam)
    assignment_role, permissions = exam_access_for_user(db, user, exam)
    allowed_actions = sorted(permission.value for permission in permissions)
    allowed_transitions = (
        sorted(_ALLOWED_STATUS_TRANSITIONS.get(exam.status, frozenset()))
        if Permission.EXAM_MANAGE in permissions
        else []
    )
    response = response.model_copy(update={
        "assignment_role": assignment_role,
        "allowed_actions": allowed_actions,
        "allowed_transitions": allowed_transitions,
    })
    if active_system_role(db, user) is None:
        assignment = db.query(models.ExamAssignment).filter_by(
            exam_id=exam.id,
            user_id=user.id,
            status="active",
        ).first()
        return response.model_copy(update={
            "is_pinned": bool(assignment and assignment.is_pinned),
            "pinned_at": assignment.pinned_at if assignment and assignment.is_pinned else None,
        })
    # Exceptional access exposes monitoring/evidence metadata, never operational
    # credentials or the external exam destination.
    return response.model_copy(update={
        "join_code": None,
        "exam_url": None,
        "google_allowed_domain": None,
        "owner_user_id": None,
    })


class ClientInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_type: Literal["desktop_cv", "browser_extension"] = "desktop_cv"
    extension_version: Optional[str] = Field(default=None, min_length=5, max_length=32)
    browser_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    device_id: Optional[UUID] = None

    @model_validator(mode="after")
    def browser_extension_fields(self) -> "ClientInfo":
        if self.client_type == "browser_extension":
            if not self.extension_version or not self.browser_name or self.device_id is None:
                raise ValueError("Extension phai gui phien ban, trinh duyet va device_id")
            _version_tuple(self.extension_version)
        return self


class JoinExamRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    join_code: str = Field(min_length=6, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    student_name: Optional[str] = Field(default=None, max_length=200)
    candidate_id: Optional[str] = Field(default=None, max_length=100)
    client_info: ClientInfo = Field(default_factory=ClientInfo)

    @field_validator("join_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("student_name")
    @classmethod
    def normalize_student_name(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_human_text(value, label="Ten thi sinh")

    @field_validator("candidate_id")
    @classmethod
    def normalize_candidate_id(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_human_text(value, label="Ma thi sinh")
        return normalized.upper() if normalized else None


class JoinExamResponse(BaseModel):
    session_token: str
    session_id: str
    exam_name: str
    student_name: str
    candidate_id: Optional[str]
    authentication_method: Literal["manual", "google"]
    exam_url: Optional[str]
    resumed: bool = False


class JoinPolicyResponse(BaseModel):
    exam_name: str
    candidate_auth_mode: Literal["manual", "google"]
    exam_url: Optional[str]
    require_extension: bool
    min_extension_version: str
    require_fullscreen: bool
    require_camera: bool
    require_microphone: bool
    require_screen_share: bool
    block_clipboard: bool
    max_focus_loss_seconds: float
    google_allowed_domain: Optional[str]
    google_login_available: bool
    server_time: datetime


class UpdateExamStatusRequest(BaseModel):
    status: Literal["draft", "scheduled", "open", "closed", "archived"]
    expected_version: Optional[int] = Field(default=None, ge=1)


class RotateJoinCodeRequest(BaseModel):
    expected_version: int = Field(ge=1)
    ttl_minutes: int = Field(default=24 * 60, ge=5, le=7 * 24 * 60)


class UpdateExamRequest(BaseModel):
    expected_version: int = Field(ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    candidate_auth_mode: Optional[Literal["manual", "google"]] = None
    exam_url: Optional[str] = Field(default=None, max_length=2048)
    google_allowed_domain: Optional[str] = Field(default=None, max_length=255)
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    require_extension: Optional[bool] = None
    min_extension_version: Optional[str] = Field(default=None, min_length=5, max_length=32)
    require_fullscreen: Optional[bool] = None
    require_camera: Optional[bool] = None
    require_microphone: Optional[bool] = None
    require_screen_share: Optional[bool] = None
    block_clipboard: Optional[bool] = None
    max_focus_loss_seconds: Optional[float] = Field(default=None, ge=0.0, le=300.0)

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = _normalize_human_text(value, label="Ten ky thi")
        if not normalized:
            raise ValueError("Ten ky thi khong duoc de trong")
        return normalized

    @field_validator("exam_url")
    @classmethod
    def validate_optional_url(cls, value: Optional[str]) -> Optional[str]:
        return _validate_exam_url(value)

    @field_validator("min_extension_version")
    @classmethod
    def validate_optional_version(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            _version_tuple(value)
        return value

    @field_validator("google_allowed_domain")
    @classmethod
    def validate_optional_google_domain(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        value = value.strip().casefold()
        if _DOMAIN_RE.fullmatch(value) is None:
            raise ValueError("Google Workspace domain khong hop le")
        return value


class ReadinessItem(BaseModel):
    code: str
    label: str
    ready: bool
    detail: str


class ExamReadinessResponse(BaseModel):
    ready: bool
    active_sessions: int
    configuration_editable: bool
    items: list[ReadinessItem]


class AssignmentRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)
    assignment_role: Literal["manager", "proctor"]
    expires_at: Optional[datetime] = None


class AssignmentResponse(BaseModel):
    id: str
    user_id: str
    email: str
    assignment_role: str
    status: str
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class EligibleMemberResponse(BaseModel):
    user_id: str
    email: str


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _assert_version(exam: models.Exam, expected_version: Optional[int]) -> None:
    if expected_version is not None and exam.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Ky thi da duoc cap nhat boi nguoi khac", "current_version": exam.version},
        )


def _assignment_response(
    assignment: models.ExamAssignment,
    user: models.User,
) -> AssignmentResponse:
    return AssignmentResponse(
        id=assignment.id,
        user_id=user.id,
        email=user.email,
        assignment_role=assignment.assignment_role,
        status=assignment.status,
        expires_at=assignment.expires_at,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


def _active_exam_by_code(db: Session, join_code: str) -> models.Exam:
    exam = db.query(models.Exam).filter(models.Exam.join_code == join_code).first()
    now = datetime.now(timezone.utc)
    if exam is None or exam.status != "open" or _as_utc(exam.join_code_expires_at) <= now:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ma tham gia khong hop le hoac da het han",
        )
    return exam


def _identity_session(
    db: Session,
    exam: models.Exam,
    *,
    candidate_number: Optional[str] = None,
    candidate_identity_id: Optional[str] = None,
) -> models.ExamSession | None:
    query = db.query(models.ExamSession).filter(models.ExamSession.exam_id == exam.id)
    if candidate_identity_id:
        query = query.filter(models.ExamSession.candidate_identity_id == candidate_identity_id)
    elif candidate_number:
        query = query.filter(models.ExamSession.candidate_number == candidate_number)
    else:
        return None
    return query.first()


@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: CreateExamRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.EXAM_CREATE)),
) -> ExamResponse:
    membership = active_membership(db, user)
    organization = db.get(models.Organization, membership.org_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay to chuc")
    overrides = {
        field_name: getattr(payload, field_name)
        for field_name in EXAM_POLICY_FIELDS
        if field_name in payload.model_fields_set
    }
    try:
        resolved_policy = resolve_exam_policy(db, organization, overrides)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    if resolved_policy.require_extension and not payload.exam_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ky thi bat buoc extension phai co URL bai thi",
        )
    if resolved_policy.candidate_auth_mode != "google" and payload.google_allowed_domain:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chi dat Google Workspace domain cho che do Google",
        )
    if resolved_policy.candidate_auth_mode == "google" and not google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend chua cau hinh Google OAuth",
        )
    exam = models.Exam(
        org_id=membership.org_id,
        name=payload.name,
        join_code=_generate_join_code(db),
        status=payload.initial_status,
        join_code_expires_at=datetime.now(timezone.utc) + timedelta(minutes=payload.join_code_ttl_minutes),
        candidate_auth_mode=resolved_policy.candidate_auth_mode,
        exam_url=payload.exam_url,
        require_extension=resolved_policy.require_extension,
        min_extension_version=resolved_policy.min_extension_version,
        require_fullscreen=resolved_policy.require_fullscreen,
        require_camera=resolved_policy.require_camera,
        require_microphone=resolved_policy.require_microphone,
        require_screen_share=resolved_policy.require_screen_share,
        block_clipboard=resolved_policy.block_clipboard,
        max_focus_loss_seconds=resolved_policy.max_focus_loss_seconds,
        google_allowed_domain=payload.google_allowed_domain,
        created_by_user_id=user.id,
        owner_user_id=user.id,
        scheduled_start_at=payload.scheduled_start_at,
        scheduled_end_at=payload.scheduled_end_at,
    )
    db.add(exam)
    db.flush()
    db.add(
        models.ExamAssignment(
            exam_id=exam.id,
            user_id=user.id,
            assignment_role="owner",
            status="active",
            assigned_by_user_id=user.id,
            is_pinned=True,
            pinned_at=datetime.now(timezone.utc),
        )
    )
    record_audit(
        db,
        actor=user,
        action="exam.create",
        resource_type="exam",
        resource_id=exam.id,
        org_id=membership.org_id,
        exam_id=exam.id,
        request=request,
        after={"name": exam.name, "status": exam.status},
    )
    db.commit()
    db.refresh(exam)
    return _exam_response_for_user(db, user, exam)


@router.get("", response_model=list[ExamResponse])
def list_exams(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[ExamResponse]:
    responses = [
        _exam_response_for_user(db, user, exam)
        for exam in scoped_exam_query(db, user, Permission.EXAM_READ).all()
    ]
    responses.sort(key=lambda item: (
        0 if item.is_pinned else 1,
        -_as_utc(item.pinned_at).timestamp() if item.pinned_at else 0,
        -_as_utc(item.updated_at).timestamp(),
    ))
    return responses


@router.get("/pinned", response_model=list[PinnedExamResponse])
def list_pinned_exams(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[PinnedExamResponse]:
    if active_system_role(db, user) is not None:
        return []
    membership = active_membership(db, user)
    if membership.role != "exam_manager":
        return []
    now = datetime.now(timezone.utc)
    rows = (
        db.query(models.ExamAssignment, models.Exam)
        .join(models.Exam, models.Exam.id == models.ExamAssignment.exam_id)
        .filter(
            models.Exam.org_id == membership.org_id,
            models.ExamAssignment.user_id == user.id,
            models.ExamAssignment.status == "active",
            models.ExamAssignment.is_pinned.is_(True),
            (
                models.ExamAssignment.expires_at.is_(None)
                | (models.ExamAssignment.expires_at > now)
            ),
        )
        .order_by(
            models.ExamAssignment.pinned_at.desc(),
            models.Exam.updated_at.desc(),
        )
        .all()
    )
    return [
        PinnedExamResponse(
            id=exam.id,
            name=exam.name,
            status=exam.status,
            assignment_role=assignment.assignment_role,
            pinned_at=assignment.pinned_at or assignment.updated_at,
        )
        for assignment, exam in rows
    ]


@router.get("/policy/defaults", response_model=OrganizationPolicy)
def get_exam_policy_defaults(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.EXAM_CREATE)),
) -> OrganizationPolicy:
    membership = active_membership(db, user)
    organization = db.get(models.Organization, membership.org_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay to chuc")
    return get_effective_organization_policy(db, organization)


@router.get("/workspace/overview", response_model=ExamWorkspaceOverviewResponse)
def get_exam_workspace_overview(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> ExamWorkspaceOverviewResponse:
    """Role-aware landing data for an exam manager's active assignments."""

    if active_system_role(db, user) is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Khong du quyen")
    membership = active_membership(db, user)
    if membership.role != "exam_manager":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Khong du quyen")

    exams = scoped_exam_query(db, user, Permission.EXAM_READ).all()
    exam_ids = [exam.id for exam in exams]
    sessions = (
        db.query(models.ExamSession)
        .filter(models.ExamSession.exam_id.in_(exam_ids))
        .all()
        if exam_ids else []
    )
    reviews = (
        db.query(models.IncidentReview)
        .join(
            models.ExamSession,
            models.ExamSession.id == models.IncidentReview.exam_session_id,
        )
        .filter(
            models.ExamSession.exam_id.in_(exam_ids),
            models.IncidentReview.status.in_(["new", "in_review"]),
        )
        .all()
        if exam_ids else []
    )

    sessions_by_exam: dict[str, list[models.ExamSession]] = {exam_id: [] for exam_id in exam_ids}
    for exam_session in sessions:
        sessions_by_exam.setdefault(exam_session.exam_id, []).append(exam_session)
    reviews_by_session: dict[str, int] = {}
    for review in reviews:
        reviews_by_session[review.exam_session_id] = reviews_by_session.get(review.exam_session_id, 0) + 1

    now = datetime.now(timezone.utc)
    workspace_items: list[ExamWorkspaceItem] = []
    assignment_roles = {"owner": 0, "manager": 0, "proctor": 0}
    exam_status = {
        item: sum(exam.status == item for exam in exams)
        for item in ("draft", "scheduled", "open", "closed", "archived")
    }

    for exam in exams:
        response = _exam_response_for_user(db, user, exam)
        assignment_role = response.assignment_role or "proctor"
        assignment_roles[assignment_role] = assignment_roles.get(assignment_role, 0) + 1
        exam_sessions = sessions_by_exam.get(exam.id, [])
        active_count = sum(
            exam_session.status in {"pending", "active", "disconnected"}
            for exam_session in exam_sessions
        )
        disconnected_count = sum(
            exam_session.status == "disconnected" for exam_session in exam_sessions
        )
        alert_count = sum(
            exam_session.session_state_current == "SESSION_ALERT"
            or exam_session.integrity_status_current == "alert"
            for exam_session in exam_sessions
            if exam_session.status in {"pending", "active", "disconnected"}
        )
        review_count = sum(reviews_by_session.get(exam_session.id, 0) for exam_session in exam_sessions)
        attention: list[str] = []
        if alert_count:
            attention.append(f"{alert_count} phiên đang cảnh báo")
        if disconnected_count:
            attention.append(f"{disconnected_count} phiên mất kết nối")
        if review_count:
            attention.append(f"{review_count} sự cố đang được xem xét")
        if (
            Permission.EXAM_MANAGE.value in response.allowed_actions
            and exam.status in {"draft", "scheduled", "open"}
            and _as_utc(exam.join_code_expires_at) <= now + timedelta(hours=24)
        ):
            attention.append("Mã tham gia sắp hết hạn")
        workspace_items.append(ExamWorkspaceItem(
            id=exam.id,
            name=exam.name,
            status=exam.status,
            assignment_role=assignment_role,
            scheduled_start_at=exam.scheduled_start_at,
            scheduled_end_at=exam.scheduled_end_at,
            join_code_expires_at=exam.join_code_expires_at,
            active_sessions=active_count,
            disconnected_sessions=disconnected_count,
            alert_sessions=alert_count,
            open_reviews=review_count,
            allowed_actions=response.allowed_actions,
            attention=attention,
        ))

    status_priority = {"open": 0, "scheduled": 1, "draft": 2, "closed": 3, "archived": 4}
    workspace_items.sort(key=lambda item: (
        0 if item.attention else 1,
        status_priority.get(item.status, 9),
        _as_utc(item.scheduled_start_at).timestamp() if item.scheduled_start_at else float("inf"),
        item.name.casefold(),
    ))
    live_statuses = {"pending", "active", "disconnected"}
    return ExamWorkspaceOverviewResponse(
        assigned_exams_total=len(exams),
        managed_exams=assignment_roles.get("owner", 0) + assignment_roles.get("manager", 0),
        proctored_exams=assignment_roles.get("proctor", 0),
        open_exams=exam_status["open"],
        scheduled_exams=exam_status["scheduled"],
        active_sessions=sum(exam_session.status in live_statuses for exam_session in sessions),
        disconnected_sessions=sum(exam_session.status == "disconnected" for exam_session in sessions),
        alert_sessions=sum(
            exam_session.status in live_statuses and (
                exam_session.session_state_current == "SESSION_ALERT"
                or exam_session.integrity_status_current == "alert"
            )
            for exam_session in sessions
        ),
        open_reviews=len(reviews),
        exam_status=exam_status,
        assignment_roles=assignment_roles,
        items=workspace_items[:8],
    )


@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam(
    exam_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> ExamResponse:
    exam = authorize_exam(db, user, exam_id, Permission.EXAM_READ)
    return _exam_response_for_user(db, user, exam)


@router.patch("/{exam_id}/pin", response_model=ExamResponse)
def update_exam_pin(
    exam_id: str,
    payload: UpdateExamPinRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> ExamResponse:
    exam = authorize_exam(db, user, exam_id, Permission.EXAM_READ)
    if active_system_role(db, user) is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Khong du quyen")
    assignment = db.query(models.ExamAssignment).filter_by(
        exam_id=exam.id,
        user_id=user.id,
        status="active",
    ).first()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay phan cong")
    if assignment.is_pinned != payload.is_pinned:
        assignment.is_pinned = payload.is_pinned
        assignment.pinned_at = datetime.now(timezone.utc) if payload.is_pinned else None
        assignment.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assignment)
    return _exam_response_for_user(db, user, exam)


@router.get("/{exam_id}/readiness", response_model=ExamReadinessResponse)
def get_exam_readiness(
    exam_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> ExamReadinessResponse:
    exam = authorize_exam(db, user, exam_id, Permission.EXAM_READ)
    now = datetime.now(timezone.utc)
    active_assignments = db.query(models.ExamAssignment).filter(
        models.ExamAssignment.exam_id == exam.id,
        models.ExamAssignment.status == "active",
        (
            models.ExamAssignment.expires_at.is_(None)
            | (models.ExamAssignment.expires_at > now)
        ),
    ).count()
    active_sessions = _active_exam_session_count(db, exam.id)
    organization = db.get(models.Organization, exam.org_id)
    quota_ready = (
        organization is None
        or organization.quota_concurrent_sessions is None
        or active_sessions < organization.quota_concurrent_sessions
    )
    schedule_ready = (
        exam.status != "scheduled"
        or (
            exam.scheduled_start_at is not None
            and exam.scheduled_end_at is not None
            and _as_utc(exam.scheduled_end_at) > _as_utc(exam.scheduled_start_at)
        )
    )
    items = [
        ReadinessItem(
            code="destination",
            label="Trang bài thi",
            ready=not exam.require_extension or bool(exam.exam_url),
            detail="Đã cấu hình URL" if exam.exam_url else "Chưa cấu hình URL bài thi",
        ),
        ReadinessItem(
            code="join_code",
            label="Mã tham gia",
            ready=_as_utc(exam.join_code_expires_at) > now,
            detail=f"Hết hạn {exam.join_code_expires_at.isoformat()}",
        ),
        ReadinessItem(
            code="schedule",
            label="Lịch thi",
            ready=schedule_ready,
            detail="Lịch hợp lệ" if schedule_ready else "Thiếu hoặc sai thời gian bắt đầu/kết thúc",
        ),
        ReadinessItem(
            code="authentication",
            label="Xác thực thí sinh",
            ready=exam.candidate_auth_mode != "google" or google_oauth_configured(),
            detail="Google OAuth" if exam.candidate_auth_mode == "google" else "Họ tên + mã thí sinh",
        ),
        ReadinessItem(
            code="staffing",
            label="Nhân sự",
            ready=active_assignments > 0,
            detail=f"{active_assignments} phân công đang hiệu lực",
        ),
        ReadinessItem(
            code="quota",
            label="Hạn mức phiên",
            ready=quota_ready,
            detail=(
                f"{active_sessions} phiên đang chiếm hạn mức"
                if organization is None or organization.quota_concurrent_sessions is None
                else f"{active_sessions}/{organization.quota_concurrent_sessions} phiên"
            ),
        ),
    ]
    return ExamReadinessResponse(
        ready=all(item.ready for item in items),
        active_sessions=active_sessions,
        configuration_editable=exam.status != "archived" and active_sessions == 0,
        items=items,
    )


@router.patch("/{exam_id}", response_model=ExamResponse)
def update_exam(
    exam_id: str,
    payload: UpdateExamRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> ExamResponse:
    exam = authorize_exam(db, user, exam_id, Permission.EXAM_MANAGE)
    _assert_version(exam, payload.expected_version)
    if exam.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ky thi da luu tru khong the sua cau hinh",
        )
    active_sessions = _active_exam_session_count(db, exam.id)
    if active_sessions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Khong the sua cau hinh khi con {active_sessions} phien dang tham gia",
        )
    before = {"name": exam.name, "version": exam.version, "status": exam.status}
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    candidate_policy = exam_policy_values(exam)
    candidate_policy.update({
        key: value
        for key, value in changes.items()
        if key in EXAM_POLICY_FIELDS
    })
    try:
        resolved_policy = resolve_exam_policy(db, exam.organization, candidate_policy)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    candidate_auth_mode = changes.get("candidate_auth_mode", exam.candidate_auth_mode)
    google_allowed_domain = changes.get("google_allowed_domain", exam.google_allowed_domain)
    exam_url = changes.get("exam_url", exam.exam_url)
    if resolved_policy.require_extension and not exam_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ky thi bat buoc extension phai co URL bai thi",
        )
    if candidate_auth_mode == "google" and not google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend chua cau hinh Google OAuth",
        )
    if candidate_auth_mode != "google" and google_allowed_domain:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chi dat Google Workspace domain cho che do Google",
        )
    start = changes.get("scheduled_start_at", exam.scheduled_start_at)
    end = changes.get("scheduled_end_at", exam.scheduled_end_at)
    if (start is None) != (end is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Phai dat ca thoi gian bat dau va ket thuc",
        )
    if start is not None and end is not None and _as_utc(end) <= _as_utc(start):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Thoi gian ket thuc phai sau thoi gian bat dau",
        )
    for field_name, value in changes.items():
        setattr(exam, field_name, value)
    if exam.require_extension and not exam.exam_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ky thi bat buoc extension phai co URL bai thi",
        )
    exam.version += 1
    exam.updated_at = datetime.now(timezone.utc)
    record_audit(
        db,
        actor=user,
        action="exam.update",
        resource_type="exam",
        resource_id=exam.id,
        org_id=exam.org_id,
        exam_id=exam.id,
        request=request,
        before=before,
        after={"name": exam.name, "version": exam.version, "status": exam.status},
    )
    db.commit()
    db.refresh(exam)
    return _exam_response_for_user(db, user, exam)


@router.get("/{exam_id}/assignments", response_model=list[AssignmentResponse])
def list_assignments(
    exam_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[AssignmentResponse]:
    authorize_exam(db, user, exam_id, Permission.EXAM_READ)
    rows = (
        db.query(models.ExamAssignment, models.User)
        .join(models.User, models.User.id == models.ExamAssignment.user_id)
        .filter(models.ExamAssignment.exam_id == exam_id)
        .order_by(models.ExamAssignment.created_at.asc())
        .all()
    )
    return [_assignment_response(assignment, member) for assignment, member in rows]


@router.get("/{exam_id}/eligible-members", response_model=list[EligibleMemberResponse])
def list_eligible_members(
    exam_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[EligibleMemberResponse]:
    exam = authorize_exam(db, user, exam_id, Permission.EXAM_ASSIGN)
    rows = (
        db.query(models.OrganizationMembership, models.User)
        .join(models.User, models.User.id == models.OrganizationMembership.user_id)
        .filter(
            models.OrganizationMembership.org_id == exam.org_id,
            models.OrganizationMembership.role == "exam_manager",
            models.OrganizationMembership.status == "active",
            models.User.status == "active",
        )
        .order_by(models.User.email.asc())
        .all()
    )
    return [EligibleMemberResponse(user_id=member.id, email=member.email) for _, member in rows]


@router.put("/{exam_id}/assignments", response_model=AssignmentResponse)
def upsert_assignment(
    exam_id: str,
    payload: AssignmentRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(get_current_user),
) -> AssignmentResponse:
    exam = authorize_exam(db, actor, exam_id, Permission.EXAM_ASSIGN)
    target_membership = db.query(models.OrganizationMembership).filter_by(
        user_id=payload.user_id,
        org_id=exam.org_id,
        status="active",
    ).first()
    target_user = db.get(models.User, payload.user_id)
    if target_membership is None or target_user is None or target_membership.role != "exam_manager":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Khong tim thay Exam Manager trong to chuc",
        )
    assignment = db.query(models.ExamAssignment).filter_by(
        exam_id=exam.id,
        user_id=target_user.id,
    ).first()
    if assignment is not None and assignment.assignment_role == "owner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Khong the thay doi owner qua endpoint phan cong",
        )
    if assignment is None:
        assignment = models.ExamAssignment(
            exam_id=exam.id,
            user_id=target_user.id,
            assignment_role=payload.assignment_role,
            status="active",
            assigned_by_user_id=actor.id,
            expires_at=payload.expires_at,
        )
        db.add(assignment)
    else:
        assignment.assignment_role = payload.assignment_role
        assignment.status = "active"
        assignment.assigned_by_user_id = actor.id
        assignment.expires_at = payload.expires_at
        assignment.updated_at = datetime.now(timezone.utc)
    db.flush()
    record_audit(
        db,
        actor=actor,
        action="exam.assignment.upsert",
        resource_type="exam_assignment",
        resource_id=assignment.id,
        org_id=exam.org_id,
        exam_id=exam.id,
        request=request,
        after={
            "user_id": target_user.id,
            "assignment_role": assignment.assignment_role,
            "status": assignment.status,
        },
    )
    db.commit()
    db.refresh(assignment)
    return _assignment_response(assignment, target_user)


@router.delete("/{exam_id}/assignments/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_assignment(
    exam_id: str,
    target_user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(get_current_user),
) -> None:
    exam = authorize_exam(db, actor, exam_id, Permission.EXAM_ASSIGN)
    if target_user_id == exam.owner_user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Khong the thu hoi owner")
    assignment = db.query(models.ExamAssignment).filter_by(
        exam_id=exam.id,
        user_id=target_user_id,
    ).first()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay phan cong")
    assignment.status = "revoked"
    assignment.updated_at = datetime.now(timezone.utc)
    record_audit(
        db,
        actor=actor,
        action="exam.assignment.revoke",
        resource_type="exam_assignment",
        resource_id=assignment.id,
        org_id=exam.org_id,
        exam_id=exam.id,
        request=request,
        before={"user_id": target_user_id, "assignment_role": assignment.assignment_role},
        after={"status": "revoked"},
    )
    db.commit()


@router.get("/join-policy/{join_code}", response_model=JoinPolicyResponse)
def get_join_policy(join_code: str, request: Request, db: Session = Depends(get_db)) -> JoinPolicyResponse:
    normalized = join_code.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{6,12}", normalized):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ma tham gia khong hop le hoac da het han")
    enforce_rate_limit(request, "join-policy-ip", limit=PUBLIC_IP_LIMIT_PER_MINUTE, window_sec=60.0)
    enforce_rate_limit(
        request, "join-policy-code", normalized, limit=JOIN_CODE_LIMIT_PER_MINUTE, window_sec=60.0,
    )
    exam = _active_exam_by_code(db, normalized)
    return JoinPolicyResponse(
        exam_name=exam.name,
        candidate_auth_mode=exam.candidate_auth_mode,
        exam_url=exam.exam_url,
        require_extension=exam.require_extension,
        min_extension_version=exam.min_extension_version,
        require_fullscreen=exam.require_fullscreen,
        require_camera=exam.require_camera,
        require_microphone=exam.require_microphone,
        require_screen_share=exam.require_screen_share,
        block_clipboard=exam.block_clipboard,
        max_focus_loss_seconds=exam.max_focus_loss_seconds,
        google_allowed_domain=exam.google_allowed_domain,
        google_login_available=google_oauth_configured(),
        server_time=datetime.now(timezone.utc),
    )


@router.post("/join", response_model=JoinExamResponse)
def join_exam(payload: JoinExamRequest, request: Request, db: Session = Depends(get_db)) -> JoinExamResponse:
    enforce_rate_limit(request, "join-ip", limit=PUBLIC_IP_LIMIT_PER_MINUTE, window_sec=60.0)
    enforce_rate_limit(
        request, "join-code", payload.join_code, limit=JOIN_CODE_LIMIT_PER_MINUTE, window_sec=60.0,
    )
    exam = _active_exam_by_code(db, payload.join_code)
    organization = db.get(models.Organization, exam.org_id)
    if organization is None or organization.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ma tham gia khong hop le hoac da het han")
    client_info = payload.client_info
    if exam.require_extension and client_info.client_type != "browser_extension":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ky thi nay bat buoc dung browser extension")
    if client_info.client_type == "browser_extension":
        assert client_info.extension_version is not None
        if _version_tuple(client_info.extension_version) < _version_tuple(exam.min_extension_version):
            raise HTTPException(
                status_code=status.HTTP_426_UPGRADE_REQUIRED,
                detail=f"Can extension phien ban {exam.min_extension_version} tro len",
            )

    candidate_identity_id: Optional[str] = None
    candidate_email: Optional[str] = None
    candidate_number: Optional[str] = None
    authentication_method = exam.candidate_auth_mode

    if exam.candidate_auth_mode == "manual":
        if not payload.student_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Vui long nhap ho ten")
        if client_info.client_type == "browser_extension" and not payload.candidate_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Vui long nhap ma thi sinh")
        student_name = payload.student_name
        candidate_number = payload.candidate_id
    else:
        if client_info.client_type != "browser_extension" or client_info.device_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Che do Google chi ho tro browser extension")
        candidate, device = resolve_candidate_token(db, bearer_token_from_request(request))
        if device.device_id_hash != hash_device_id(str(client_info.device_id)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token khong thuoc cai dat extension nay")
        if exam.google_allowed_domain and candidate.hosted_domain != exam.google_allowed_domain:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Ky thi chi chap nhan tai khoan Google Workspace {exam.google_allowed_domain}",
            )
        student_name = candidate.display_name
        candidate_email = candidate.email
        candidate_identity_id = candidate.id

    device_hash = (
        hash_device_id(str(client_info.device_id)) if client_info.device_id is not None else None
    )
    existing = _identity_session(
        db,
        exam,
        candidate_number=candidate_number,
        candidate_identity_id=candidate_identity_id,
    )
    if existing is not None:
        if (
            client_info.client_type != "browser_extension"
            or not device_hash
            or existing.device_id_hash != device_hash
            or existing.status not in {"pending", "active", "disconnected"}
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Danh tinh nay da duoc su dung cho ky thi",
            )
        existing.status = "pending"
        existing.disconnect_reason = None
        existing.last_seen_at = datetime.now(timezone.utc)
        existing.extension_version = client_info.extension_version
        existing.browser_name = client_info.browser_name
        db.commit()
        db.refresh(existing)
        return JoinExamResponse(
            session_token=create_session_token(existing.id),
            session_id=existing.id,
            exam_name=exam.name,
            student_name=existing.student_name,
            candidate_id=existing.candidate_number,
            authentication_method=existing.authentication_method,
            exam_url=exam.exam_url,
            resumed=True,
        )

    if organization.quota_concurrent_sessions is not None:
        active_count = (
            db.query(models.ExamSession)
            .join(models.Exam, models.Exam.id == models.ExamSession.exam_id)
            .filter(
                models.Exam.org_id == organization.id,
                models.ExamSession.status.in_(["pending", "active", "disconnected"]),
            )
            .count()
        )
        if active_count >= organization.quota_concurrent_sessions:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="To chuc da dat han muc phien thi dong thoi",
            )
    session = models.ExamSession(
        exam_id=exam.id,
        student_name=student_name,
        candidate_number=candidate_number,
        candidate_email=candidate_email,
        candidate_identity_id=candidate_identity_id,
        authentication_method=authentication_method,
        client_type=client_info.client_type,
        extension_version=client_info.extension_version,
        browser_name=client_info.browser_name,
        device_id_hash=device_hash,
        camera_status="pending" if exam.require_camera else "not_required",
        microphone_status="pending" if exam.require_microphone else "not_required",
        screen_share_status="pending" if exam.require_screen_share else "not_required",
        status="pending",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(session)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Danh tinh nay da duoc su dung cho ky thi",
        ) from exc
    db.refresh(session)

    return JoinExamResponse(
        session_token=create_session_token(session.id),
        session_id=session.id,
        exam_name=exam.name,
        student_name=session.student_name,
        candidate_id=session.candidate_number,
        authentication_method=authentication_method,
        exam_url=exam.exam_url,
    )


@router.patch("/{exam_id}/status", response_model=ExamResponse)
def update_exam_status(
    exam_id: str,
    payload: UpdateExamStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> ExamResponse:
    exam = authorize_exam(db, user, exam_id, Permission.EXAM_MANAGE)
    _assert_version(exam, payload.expected_version)
    if payload.status != exam.status and payload.status not in _ALLOWED_STATUS_TRANSITIONS.get(
        exam.status,
        frozenset(),
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Khong the chuyen ky thi tu {exam.status} sang {payload.status}",
        )
    if payload.status == "scheduled" and (
        exam.scheduled_start_at is None or exam.scheduled_end_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ky thi scheduled phai co lich bat dau/ket thuc",
        )
    if payload.status == "open" and _as_utc(exam.join_code_expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ma tham gia da het han; hay xoay ma truoc khi mo ky thi",
        )
    if payload.status == exam.status:
        return _exam_response_for_user(db, user, exam)
    previous_status = exam.status
    exam.status = payload.status
    exam.archived_at = datetime.now(timezone.utc) if payload.status == "archived" else None
    exam.version += 1
    exam.updated_at = datetime.now(timezone.utc)
    record_audit(
        db,
        actor=user,
        action="exam.status.update",
        resource_type="exam",
        resource_id=exam.id,
        org_id=exam.org_id,
        exam_id=exam.id,
        request=request,
        before={"status": previous_status},
        after={"status": exam.status, "version": exam.version},
    )
    db.commit()
    db.refresh(exam)
    return _exam_response_for_user(db, user, exam)


@router.post("/{exam_id}/rotate-code", response_model=ExamResponse)
def rotate_join_code(
    exam_id: str,
    payload: RotateJoinCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> ExamResponse:
    exam = authorize_exam(db, user, exam_id, Permission.EXAM_MANAGE)
    _assert_version(exam, payload.expected_version)
    if exam.status == "archived":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ky thi da luu tru")
    exam.join_code = _generate_join_code(db)
    exam.join_code_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=payload.ttl_minutes,
    )
    exam.version += 1
    exam.updated_at = datetime.now(timezone.utc)
    record_audit(
        db,
        actor=user,
        action="exam.join_code.rotate",
        resource_type="exam",
        resource_id=exam.id,
        org_id=exam.org_id,
        exam_id=exam.id,
        request=request,
        after={"status": exam.status, "expires_at": exam.join_code_expires_at, "version": exam.version},
    )
    db.commit()
    db.refresh(exam)
    return _exam_response_for_user(db, user, exam)
