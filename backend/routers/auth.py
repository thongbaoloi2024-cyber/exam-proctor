"""Dang ky (tao Organization + admin dau tien) va dang nhap cho admin/proctor.
Hoc sinh khong dung router nay - xem exams.py:join_exam.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from .. import models
from ..auth import (
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    set_auth_cookie,
    verify_password,
)
from ..db import get_db
from ..rate_limit import (
    LOGIN_ACCOUNT_LIMIT_PER_MINUTE,
    PUBLIC_IP_LIMIT_PER_MINUTE,
    enforce_rate_limit,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=200)
    admin_email: str = Field(min_length=3, max_length=255)
    admin_password: str = Field(min_length=8, max_length=72)

    @field_validator("organization_name", "admin_email")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Truong khong duoc de trong")
        return value

    @field_validator("admin_email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("Email khong hop le")
        return value.casefold()

    @field_validator("admin_password")
    @classmethod
    def bcrypt_password_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Mat khau vuot qua gioi han 72 byte")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()

    @field_validator("password")
    @classmethod
    def bcrypt_password_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Mat khau vuot qua gioi han 72 byte")
        return value


class CreateProctorRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if "@" not in value:
            raise ValueError("Email khong hop le")
        return value

    @field_validator("password")
    @classmethod
    def bcrypt_password_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Mat khau vuot qua gioi han 72 byte")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    org_id: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    email: str
    role: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    enforce_rate_limit(
        request, "register-ip", limit=PUBLIC_IP_LIMIT_PER_MINUTE, window_sec=60.0,
    )
    existing = db.query(models.User).filter(models.User.email == payload.admin_email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email da duoc dang ky")

    org = models.Organization(name=payload.organization_name)
    db.add(org)
    db.flush()

    admin = models.User(
        org_id=org.id,
        email=payload.admin_email,
        password_hash=hash_password(payload.admin_password),
        role="admin",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    token = create_access_token(admin.id, admin.role, admin.org_id)
    set_auth_cookie(response, token)
    return TokenResponse(access_token=token, role=admin.role, org_id=admin.org_id)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    enforce_rate_limit(
        request, "login-ip", limit=PUBLIC_IP_LIMIT_PER_MINUTE, window_sec=60.0,
    )
    enforce_rate_limit(
        request,
        "login-account",
        payload.email,
        limit=LOGIN_ACCOUNT_LIMIT_PER_MINUTE,
        window_sec=60.0,
    )
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai email hoac mat khau")

    token = create_access_token(user.id, user.role, user.org_id)
    set_auth_cookie(response, token)
    return TokenResponse(access_token=token, role=user.role, org_id=user.org_id)


@router.get("/me", response_model=UserResponse)
def me(user: models.User = Depends(get_current_user)) -> models.User:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    clear_auth_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/proctors", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_proctor(
    payload: CreateProctorRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
) -> models.User:
    """Chi admin tao duoc tai khoan proctor, luon gan vao dung org cua chinh
    admin do (khong nhan org_id tu client) - day la diem cach ly multi-tenant
    quan trong nhat cua endpoint nay."""
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email da duoc dang ky")

    proctor = models.User(
        org_id=admin.org_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="proctor",
    )
    db.add(proctor)
    db.commit()
    db.refresh(proctor)
    return proctor
