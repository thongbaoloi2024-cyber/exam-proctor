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
from ..rate_limit import JOIN_CODE_LIMIT_PER_MINUTE, PUBLIC_IP_LIMIT_PER_MINUTE, enforce_rate_limit
from .candidate_auth import google_oauth_configured

router = APIRouter(prefix="/exams", tags=["exams"])

_JOIN_CODE_ALPHABET = string.ascii_uppercase + string.digits
_JOIN_CODE_LENGTH = 6
_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")
_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")


def _generate_join_code(db: Session) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(_JOIN_CODE_ALPHABET) for _ in range(_JOIN_CODE_LENGTH))
        if db.query(models.Exam).filter(models.Exam.join_code == code).first() is None:
            return code
    raise RuntimeError("Khong sinh duoc join_code duy nhat sau 20 lan thu")


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
        if self.require_extension and not self.exam_url:
            raise ValueError("Ky thi bat buoc extension phai co URL bai thi")
        if self.candidate_auth_mode == "google" and not self.require_extension:
            raise ValueError("Che do Google bat buoc su dung browser extension")
        if self.candidate_auth_mode != "google" and self.google_allowed_domain:
            raise ValueError("Chi dat Google Workspace domain cho che do Google")
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


def _exam_response_for_user(
    db: Session,
    user: models.User,
    exam: models.Exam,
) -> ExamResponse:
    response = ExamResponse.model_validate(exam)
    if active_system_role(db, user) is None:
        return response
    # Break-glass exposes monitoring/evidence metadata, never operational
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


class UpdateExamRequest(BaseModel):
    expected_version: int = Field(ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    exam_url: Optional[str] = Field(default=None, max_length=2048)
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


def _ensure_identity_not_used(
    db: Session,
    exam: models.Exam,
    *,
    candidate_number: Optional[str] = None,
    candidate_identity_id: Optional[str] = None,
) -> None:
    query = db.query(models.ExamSession).filter(models.ExamSession.exam_id == exam.id)
    if candidate_identity_id:
        query = query.filter(models.ExamSession.candidate_identity_id == candidate_identity_id)
    elif candidate_number:
        query = query.filter(models.ExamSession.candidate_number == candidate_number)
    else:
        return
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Danh tinh nay da duoc su dung cho ky thi",
        )


@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: CreateExamRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.EXAM_CREATE)),
) -> models.Exam:
    if payload.candidate_auth_mode == "google" and not google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend chua cau hinh Google OAuth",
        )
    membership = active_membership(db, user)
    exam = models.Exam(
        org_id=membership.org_id,
        name=payload.name,
        join_code=_generate_join_code(db),
        status=payload.initial_status,
        join_code_expires_at=datetime.now(timezone.utc) + timedelta(minutes=payload.join_code_ttl_minutes),
        candidate_auth_mode=payload.candidate_auth_mode,
        exam_url=payload.exam_url,
        require_extension=payload.require_extension,
        min_extension_version=payload.min_extension_version,
        require_fullscreen=payload.require_fullscreen,
        require_camera=payload.require_camera,
        require_microphone=payload.require_microphone,
        require_screen_share=payload.require_screen_share,
        block_clipboard=payload.block_clipboard,
        max_focus_loss_seconds=payload.max_focus_loss_seconds,
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
    return exam


@router.get("", response_model=list[ExamResponse])
def list_exams(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[ExamResponse]:
    return [
        _exam_response_for_user(db, user, exam)
        for exam in scoped_exam_query(db, user, Permission.EXAM_READ).all()
    ]


@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam(
    exam_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> ExamResponse:
    exam = authorize_exam(db, user, exam_id, Permission.EXAM_READ)
    return _exam_response_for_user(db, user, exam)


@router.patch("/{exam_id}", response_model=ExamResponse)
def update_exam(
    exam_id: str,
    payload: UpdateExamRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.Exam:
    exam = authorize_exam(db, user, exam_id, Permission.EXAM_MANAGE)
    if exam.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chi duoc sua cau hinh day du khi ky thi o trang thai draft",
        )
    _assert_version(exam, payload.expected_version)
    before = {"name": exam.name, "version": exam.version, "status": exam.status}
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
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
    return exam


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
        _ensure_identity_not_used(db, exam, candidate_number=candidate_number)
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
        _ensure_identity_not_used(db, exam, candidate_identity_id=candidate.id)

    device_hash = (
        hash_device_id(str(client_info.device_id)) if client_info.device_id is not None else None
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
) -> models.Exam:
    exam = authorize_exam(db, user, exam_id, Permission.EXAM_MANAGE)
    _assert_version(exam, payload.expected_version)
    transitions = {
        "draft": {"scheduled", "open", "archived"},
        "scheduled": {"draft", "open", "closed"},
        "open": {"closed"},
        "closed": {"open", "archived"},
        "archived": set(),
    }
    if payload.status != exam.status and payload.status not in transitions.get(exam.status, set()):
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
        return exam
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
    return exam


@router.post("/{exam_id}/rotate-code", response_model=ExamResponse)
def rotate_join_code(
    exam_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.Exam:
    exam = authorize_exam(db, user, exam_id, Permission.EXAM_MANAGE)
    if exam.status == "archived":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ky thi da luu tru")
    exam.join_code = _generate_join_code(db)
    exam.join_code_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    exam.status = "open"
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
        after={"status": exam.status, "expires_at": exam.join_code_expires_at},
    )
    db.commit()
    db.refresh(exam)
    return exam
