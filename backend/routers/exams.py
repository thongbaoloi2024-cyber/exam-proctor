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
from ..auth import create_session_token, require_role
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
        return self


class ExamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    join_code: str
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
    status: Literal["open", "closed"]


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _active_exam_by_code(db: Session, join_code: str) -> models.Exam:
    exam = db.query(models.Exam).filter(models.Exam.join_code == join_code).first()
    now = datetime.now(timezone.utc)
    if exam is None or exam.status != "open" or _as_utc(exam.join_code_expires_at) <= now:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ma tham gia khong hop le hoac da het han",
        )
    return exam


def _get_owned_exam(db: Session, exam_id: str, user: models.User) -> models.Exam:
    exam = db.get(models.Exam, exam_id)
    if exam is None or exam.org_id != user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay ky thi")
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
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("admin", "proctor")),
) -> models.Exam:
    if payload.candidate_auth_mode == "google" and not google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend chua cau hinh Google OAuth",
        )
    exam = models.Exam(
        org_id=user.org_id,
        name=payload.name,
        join_code=_generate_join_code(db),
        status="open",
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
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.get("", response_model=list[ExamResponse])
def list_exams(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("admin", "proctor")),
) -> list[models.Exam]:
    return db.query(models.Exam).filter(models.Exam.org_id == user.org_id).all()


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
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("admin", "proctor")),
) -> models.Exam:
    exam = _get_owned_exam(db, exam_id, user)
    exam.status = payload.status
    db.commit()
    db.refresh(exam)
    return exam


@router.post("/{exam_id}/rotate-code", response_model=ExamResponse)
def rotate_join_code(
    exam_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("admin", "proctor")),
) -> models.Exam:
    exam = _get_owned_exam(db, exam_id, user)
    exam.join_code = _generate_join_code(db)
    exam.join_code_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    exam.status = "open"
    db.commit()
    db.refresh(exam)
    return exam
