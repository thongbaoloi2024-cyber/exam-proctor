"""Dang ky (tao Organization + admin dau tien) va dang nhap cho admin/proctor.
Hoc sinh khong dung router nay - xem exams.py:join_exam.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from .. import models
from ..auth import (
    AUTH_FLOW_COOKIE_NAME,
    clear_auth_flow_cookie,
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    set_auth_cookie,
    set_auth_flow_cookie,
    verify_password,
)
from ..authorization import (
    Permission,
    active_membership,
    active_system_role,
    capabilities_for_user,
    require_permission,
)
from ..audit import record_audit
from ..db import get_db
from ..rate_limit import (
    LOGIN_ACCOUNT_LIMIT_PER_MINUTE,
    PUBLIC_IP_LIMIT_PER_MINUTE,
    enforce_rate_limit,
)
from ..mfa import (
    consume_recovery_code,
    decrypt_secret,
    encrypt_secret,
    generate_recovery_codes,
    generate_secret,
    provisioning_uri,
    qr_code_data_url,
    verify_totp,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_AUTH_CHALLENGE_TTL_MINUTES = 10
_OAUTH_STATE_TTL_MINUTES = 10
_MAX_MFA_ATTEMPTS = 3


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
    mfa_setup_required: bool = False


class LoginResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    role: str | None = None
    org_id: str | None = None
    mfa_required: bool = False
    mfa_setup_required: bool = False


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)

    @field_validator("code")
    @classmethod
    def strip_code(cls, value: str) -> str:
        return value.strip()


class GoogleRegistrationCompleteRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=200)

    @field_validator("organization_name")
    @classmethod
    def strip_organization_name(cls, value: str) -> str:
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("Ten to chuc khong duoc de trong")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    email: str
    role: str


class CurrentUserResponse(UserResponse):
    effective_role: str
    active_org_id: str
    is_system_admin: bool
    capabilities: list[str]


class AcceptInvitationRequest(BaseModel):
    invitation_token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def invitation_password_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Mat khau vuot qua gioi han 72 byte")
        return value


class MyOrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str | None
    role: str
    membership_status: str


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_code_data_url: str
    recovery_codes: list[str]


class MfaConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _safe_claim_text(claims: dict[str, Any], key: str, maximum: int) -> str | None:
    value = claims.get(key)
    if not isinstance(value, str):
        return None
    value = " ".join(value.strip().split())
    return value[:maximum] or None


def _create_auth_challenge(
    db: Session,
    purpose: str,
    *,
    user_id: str | None = None,
    google_subject: str | None = None,
    google_email: str | None = None,
    google_display_name: str | None = None,
    google_avatar_url: str | None = None,
) -> str:
    raw_token = secrets.token_urlsafe(48)
    now = _now()
    db.add(
        models.WebAuthChallenge(
            token_hash=_sha256(raw_token),
            purpose=purpose,
            user_id=user_id,
            google_subject=google_subject,
            google_email=google_email,
            google_display_name=google_display_name,
            google_avatar_url=google_avatar_url,
            created_at=now,
            expires_at=now + timedelta(minutes=_AUTH_CHALLENGE_TTL_MINUTES),
        )
    )
    db.commit()
    return raw_token


def _resolve_auth_challenge(
    request: Request,
    db: Session,
    purpose: str,
) -> models.WebAuthChallenge | None:
    raw_token = request.cookies.get(AUTH_FLOW_COOKIE_NAME)
    if not raw_token:
        return None
    challenge = db.query(models.WebAuthChallenge).filter_by(token_hash=_sha256(raw_token)).first()
    if (
        challenge is None
        or challenge.purpose != purpose
        or challenge.consumed_at is not None
        or _as_utc(challenge.expires_at) <= _now()
    ):
        return None
    return challenge


def _login_system_role(db: Session, user: models.User) -> models.SystemRole | None:
    return db.query(models.SystemRole).filter_by(
        user_id=user.id,
        role="system_admin",
    ).first()


def _validate_login_identity(db: Session, user: models.User) -> models.SystemRole | None:
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tai khoan khong hoat dong")
    system_role = _login_system_role(db, user)
    is_system_identity = system_role is not None and system_role.status in {"active", "pending_mfa"}
    organization = db.get(models.Organization, user.org_id)
    if (organization is None or organization.status != "active") and not is_system_identity:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="To chuc dang bi khoa")
    return system_role


def _issue_login_session(
    db: Session,
    user: models.User,
    response: Response,
    *,
    mfa_reenrollment_required: bool = False,
) -> LoginResponse:
    system_role = _login_system_role(db, user)
    if system_role is not None and system_role.status == "pending_mfa" and user.mfa_enabled:
        system_role.status = "active"
        system_role.updated_at = _now()
        db.commit()
    effective_role = (
        "system_admin"
        if system_role is not None and system_role.status == "active"
        else user.role
    )
    token = create_access_token(user.id, user.role, user.org_id, user.session_version)
    set_auth_cookie(response, token)
    clear_auth_flow_cookie(response)
    return LoginResponse(
        access_token=token,
        role=effective_role,
        org_id=user.org_id,
        mfa_setup_required=(
            mfa_reenrollment_required
            or (
                system_role is not None
                and system_role.status == "pending_mfa"
                and not user.mfa_enabled
            )
        ),
    )


@dataclass(frozen=True)
class WebGoogleOAuthSettings:
    client_id: str
    client_secret: str
    callback_url: str


def _web_google_settings() -> WebGoogleOAuthSettings | None:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    callback_url = os.environ.get("GOOGLE_WEB_OAUTH_CALLBACK_URL", "").strip()
    # Shared Google credentials may be configured for the candidate extension
    # only. The web flow is enabled by its own callback setting.
    if not callback_url:
        return None
    if not all((client_id, client_secret, callback_url)):
        raise RuntimeError(
            "Google OAuth web can GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET "
            "va GOOGLE_WEB_OAUTH_CALLBACK_URL"
        )
    return WebGoogleOAuthSettings(client_id, client_secret, callback_url)


def validate_web_google_oauth_configuration() -> None:
    settings = _web_google_settings()
    if settings is None:
        return
    callback = urlsplit(settings.callback_url)
    production = os.environ.get("APP_ENV", "development").strip().lower() == "production"
    if callback.scheme not in ({"https"} if production else {"http", "https"}) or not callback.netloc:
        raise RuntimeError("GOOGLE_WEB_OAUTH_CALLBACK_URL khong hop le")


def web_google_oauth_configured() -> bool:
    return _web_google_settings() is not None


def _require_web_google_settings() -> WebGoogleOAuthSettings:
    settings = _web_google_settings()
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dang nhap Google cho web chua duoc cau hinh",
        )
    return settings


def _exchange_and_verify_web_google(
    code: str,
    verifier: str,
    nonce: str,
    settings: WebGoogleOAuthSettings,
) -> dict[str, Any]:
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
            "redirect_uri": settings.callback_url,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    raw_id_token = response.json().get("id_token")
    if not isinstance(raw_id_token, str):
        raise ValueError("Google khong tra ve id_token")

    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token as google_id_token

    try:
        claims = google_id_token.verify_oauth2_token(
            raw_id_token,
            GoogleRequest(),
            settings.client_id,
            clock_skew_in_seconds=30,
        )
    except Exception as exc:
        raise ValueError("Google ID token khong hop le") from exc
    if claims.get("nonce") != nonce:
        raise ValueError("OIDC nonce khong khop")
    return dict(claims)


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
    # Slug is generated server-side and includes the UUID prefix, so tenant
    # names do not need to be globally unique during the compatibility phase.
    org.slug = f"org-{org.id.replace('-', '')[:12]}"

    admin = models.User(
        org_id=org.id,
        email=payload.admin_email,
        password_hash=hash_password(payload.admin_password),
        role="admin",
    )
    db.add(admin)
    db.flush()
    db.add(
        models.OrganizationMembership(
            user_id=admin.id,
            org_id=org.id,
            role="org_admin",
            status="active",
        )
    )
    db.commit()
    db.refresh(admin)

    token = create_access_token(admin.id, admin.role, admin.org_id, admin.session_version)
    set_auth_cookie(response, token)
    return TokenResponse(access_token=token, role=admin.role, org_id=admin.org_id)


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
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
    if user is None or user.status != "active" or not verify_password(payload.password, user.password_hash):
        record_audit(
            db,
            actor=user,
            action="security.login.failed",
            resource_type="user_account",
            resource_id=user.id if user else payload.email,
            org_id=user.org_id if user else None,
            outcome="failure",
            reason="invalid_credentials_or_inactive_account",
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai email hoac mat khau")
    _validate_login_identity(db, user)
    if user.mfa_enabled:
        clear_auth_cookie(response)
        challenge_token = _create_auth_challenge(db, "mfa_login", user_id=user.id)
        set_auth_flow_cookie(response, challenge_token, _AUTH_CHALLENGE_TTL_MINUTES * 60)
        return LoginResponse(mfa_required=True)

    login_response = _issue_login_session(db, user, response)
    record_audit(
        db,
        actor=user,
        action="security.login.success",
        resource_type="user_account",
        resource_id=user.id,
        org_id=user.org_id,
        request=request,
    )
    db.commit()
    return login_response


@router.get("/mfa/challenge")
def mfa_challenge_status(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    challenge = _resolve_auth_challenge(request, db, "mfa_login")
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phien MFA da het han")
    user = db.get(models.User, challenge.user_id)
    if user is None or not user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phien MFA khong hop le")
    return {
        "email": user.email,
        "attempts_remaining": max(0, _MAX_MFA_ATTEMPTS - challenge.failed_attempts),
    }


@router.post("/mfa/verify")
def verify_login_mfa(
    payload: MfaVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    challenge = _resolve_auth_challenge(request, db, "mfa_login")
    if challenge is None or challenge.user_id is None:
        result = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Phien MFA da het han. Vui long dang nhap lai.", "attempts_remaining": 0},
        )
        clear_auth_flow_cookie(result)
        return result

    user = db.get(models.User, challenge.user_id)
    if user is None or not user.mfa_enabled:
        result = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Phien MFA khong hop le.", "attempts_remaining": 0},
        )
        clear_auth_flow_cookie(result)
        return result
    try:
        _validate_login_identity(db, user)
    except HTTPException as exc:
        result = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        clear_auth_flow_cookie(result)
        return result

    submitted_code = payload.code
    recovery_verified, remaining_codes = consume_recovery_code(
        user.mfa_recovery_codes_json,
        submitted_code,
    )
    totp_verified = False
    secret_error = False
    if not recovery_verified:
        if user.mfa_secret_encrypted:
            try:
                totp_verified = verify_totp(decrypt_secret(user.mfa_secret_encrypted), submitted_code)
            except ValueError:
                secret_error = True
        else:
            secret_error = True

    if not recovery_verified and not totp_verified:
        challenge.failed_attempts += 1
        attempts_remaining = max(0, _MAX_MFA_ATTEMPTS - challenge.failed_attempts)
        if attempts_remaining == 0:
            challenge.consumed_at = _now()
        record_audit(
            db,
            actor=user,
            action="security.mfa.failed",
            resource_type="user_account",
            resource_id=user.id,
            org_id=user.org_id,
            outcome="failure",
            reason="invalid_mfa_code",
            request=request,
        )
        db.commit()
        detail = (
            "Khong giai ma duoc MFA secret; hay dung recovery code hoac lien he quan tri vien."
            if secret_error
            else "Ma MFA hoac recovery code khong hop le."
        )
        result = JSONResponse(
            status_code=(status.HTTP_409_CONFLICT if secret_error else status.HTTP_401_UNAUTHORIZED),
            content={"detail": detail, "attempts_remaining": attempts_remaining},
        )
        if attempts_remaining == 0:
            clear_auth_flow_cookie(result)
        return result

    mfa_reenrollment_required = False
    if recovery_verified:
        secret_readable = False
        if user.mfa_secret_encrypted:
            try:
                decrypt_secret(user.mfa_secret_encrypted)
                secret_readable = True
            except ValueError:
                secret_readable = False
        if secret_readable:
            user.mfa_recovery_codes_json = remaining_codes
        else:
            user.mfa_enabled = False
            user.mfa_secret_encrypted = None
            user.mfa_recovery_codes_json = None
            user.session_version += 1
            user.updated_at = _now()
            system_role = _login_system_role(db, user)
            if system_role is not None and system_role.status == "active":
                system_role.status = "pending_mfa"
                system_role.updated_at = _now()
            mfa_reenrollment_required = True

    challenge.consumed_at = _now()
    record_audit(
        db,
        actor=user,
        action="security.mfa.success",
        resource_type="user_account",
        resource_id=user.id,
        org_id=user.org_id,
        request=request,
    )
    db.commit()
    login_data = _issue_login_session(
        db,
        user,
        Response(),
        mfa_reenrollment_required=mfa_reenrollment_required,
    )
    result = JSONResponse(status_code=status.HTTP_200_OK, content=login_data.model_dump())
    set_auth_cookie(result, login_data.access_token or "")
    clear_auth_flow_cookie(result)
    return result


def _google_error_redirect(flow: str, error: str) -> RedirectResponse:
    page = "/ui/register" if flow == "register" else "/ui/login"
    return RedirectResponse(f"{page}?error={error}", status_code=status.HTTP_302_FOUND)


@router.get("/google/start")
def start_web_google_auth(
    request: Request,
    flow: Literal["login", "register"] = Query(default="login"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    enforce_rate_limit(
        request,
        "web-google-start",
        limit=LOGIN_ACCOUNT_LIMIT_PER_MINUTE,
        window_sec=60.0,
    )
    settings = _require_web_google_settings()
    now = _now()
    db.query(models.WebOAuthTransaction).filter(
        models.WebOAuthTransaction.expires_at < now,
    ).delete(synchronize_session=False)

    state_value = secrets.token_urlsafe(48)
    verifier = secrets.token_urlsafe(64)
    nonce = secrets.token_urlsafe(32)
    db.add(
        models.WebOAuthTransaction(
            state_hash=_sha256(state_value),
            flow=flow,
            pkce_verifier=verifier,
            oidc_nonce=nonce,
            created_at=now,
            expires_at=now + timedelta(minutes=_OAUTH_STATE_TTL_MINUTES),
        )
    )
    db.commit()
    query = urlencode(
        {
            "client_id": settings.client_id,
            "redirect_uri": settings.callback_url,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state_value,
            "nonce": nonce,
            "code_challenge": _pkce_challenge(verifier),
            "code_challenge_method": "S256",
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return RedirectResponse(
        f"https://accounts.google.com/o/oauth2/v2/auth?{query}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/google/callback")
def web_google_callback(
    request: Request,
    state_value: str = Query(alias="state", min_length=16, max_length=512),
    code: str | None = Query(default=None, min_length=1, max_length=4096),
    error: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    enforce_rate_limit(
        request,
        "web-google-callback",
        limit=LOGIN_ACCOUNT_LIMIT_PER_MINUTE * 2,
        window_sec=60.0,
    )
    settings = _require_web_google_settings()
    transaction = db.query(models.WebOAuthTransaction).filter_by(
        state_hash=_sha256(state_value),
    ).first()
    now = _now()
    if (
        transaction is None
        or transaction.completed_at is not None
        or _as_utc(transaction.expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state khong hop le hoac da het han",
        )
    flow = transaction.flow
    if error or not code:
        transaction.completed_at = now
        db.commit()
        return _google_error_redirect(flow, "google_cancelled")

    try:
        claims = _exchange_and_verify_web_google(
            code,
            transaction.pkce_verifier,
            transaction.oidc_nonce,
            settings,
        )
    except (httpx.HTTPError, ValueError, KeyError):
        transaction.completed_at = now
        db.commit()
        return _google_error_redirect(flow, "google_verification_failed")

    subject = _safe_claim_text(claims, "sub", 255)
    email = _safe_claim_text(claims, "email", 255)
    display_name = _safe_claim_text(claims, "name", 200) or email
    avatar_url = _safe_claim_text(claims, "picture", 2048)
    if not subject or not email or claims.get("email_verified") is not True:
        transaction.completed_at = now
        db.commit()
        return _google_error_redirect(flow, "google_email_not_verified")
    normalized_email = email.casefold()
    transaction.completed_at = now

    subject_user = db.query(models.User).filter_by(google_subject=subject).first()
    email_user = db.query(models.User).filter_by(email=normalized_email).first()
    if subject_user is not None and email_user is not None and subject_user.id != email_user.id:
        db.commit()
        return _google_error_redirect(flow, "google_identity_conflict")
    user = subject_user or email_user

    if flow == "register":
        if user is not None:
            db.commit()
            return _google_error_redirect(flow, "account_exists")
        challenge_token = _create_auth_challenge(
            db,
            "google_registration",
            google_subject=subject,
            google_email=normalized_email,
            google_display_name=display_name,
            google_avatar_url=avatar_url,
        )
        redirect = RedirectResponse(
            "/ui/register/organization",
            status_code=status.HTTP_302_FOUND,
        )
        set_auth_flow_cookie(redirect, challenge_token, _AUTH_CHALLENGE_TTL_MINUTES * 60)
        return redirect

    if user is None:
        challenge_token = _create_auth_challenge(
            db,
            "google_registration",
            google_subject=subject,
            google_email=normalized_email,
            google_display_name=display_name,
            google_avatar_url=avatar_url,
        )
        redirect = RedirectResponse(
            "/ui/register/organization?source=login",
            status_code=status.HTTP_302_FOUND,
        )
        set_auth_flow_cookie(redirect, challenge_token, _AUTH_CHALLENGE_TTL_MINUTES * 60)
        return redirect

    if user.google_subject is not None and user.google_subject != subject:
        db.commit()
        return _google_error_redirect(flow, "google_identity_conflict")
    user.google_subject = subject
    user.updated_at = now
    try:
        _validate_login_identity(db, user)
    except HTTPException:
        db.commit()
        return _google_error_redirect(flow, "account_unavailable")
    db.commit()

    if user.mfa_enabled:
        challenge_token = _create_auth_challenge(db, "mfa_login", user_id=user.id)
        redirect = RedirectResponse("/ui/mfa/verify", status_code=status.HTTP_302_FOUND)
        clear_auth_cookie(redirect)
        set_auth_flow_cookie(redirect, challenge_token, _AUTH_CHALLENGE_TTL_MINUTES * 60)
        return redirect

    redirect = RedirectResponse("/ui/exams/overview", status_code=status.HTTP_302_FOUND)
    login_data = _issue_login_session(db, user, redirect)
    redirect.headers["location"] = (
        "/ui/mfa"
        if login_data.mfa_setup_required
        else "/ui/system"
        if login_data.role == "system_admin"
        else "/ui/organization/overview"
        if login_data.role in {"admin", "org_admin"}
        else "/ui/exams/overview"
    )
    return redirect


@router.get("/google/registration")
def google_registration_status(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    challenge = _resolve_auth_challenge(request, db, "google_registration")
    if challenge is None or not challenge.google_email or not challenge.google_subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phien dang ky da het han")
    return {
        "email": challenge.google_email,
        "display_name": challenge.google_display_name,
        "avatar_url": challenge.google_avatar_url,
    }


@router.post(
    "/google/register/complete",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def complete_google_registration(
    payload: GoogleRegistrationCompleteRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    enforce_rate_limit(
        request,
        "google-register-complete",
        limit=PUBLIC_IP_LIMIT_PER_MINUTE,
        window_sec=60.0,
    )
    challenge = _resolve_auth_challenge(request, db, "google_registration")
    if challenge is None or not challenge.google_email or not challenge.google_subject:
        clear_auth_flow_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phien dang ky da het han")
    existing = db.query(models.User).filter(
        (models.User.email == challenge.google_email)
        | (models.User.google_subject == challenge.google_subject)
    ).first()
    if existing is not None:
        challenge.consumed_at = _now()
        db.commit()
        clear_auth_flow_cookie(response)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tai khoan da ton tai")

    org = models.Organization(name=payload.organization_name)
    db.add(org)
    db.flush()
    org.slug = f"org-{org.id.replace('-', '')[:12]}"
    admin = models.User(
        org_id=org.id,
        email=challenge.google_email,
        password_hash=hash_password(secrets.token_urlsafe(48)),
        google_subject=challenge.google_subject,
        role="admin",
    )
    db.add(admin)
    db.flush()
    db.add(
        models.OrganizationMembership(
            user_id=admin.id,
            org_id=org.id,
            role="org_admin",
            status="active",
        )
    )
    challenge.consumed_at = _now()
    db.commit()
    db.refresh(admin)
    token = create_access_token(admin.id, admin.role, admin.org_id, admin.session_version)
    set_auth_cookie(response, token)
    clear_auth_flow_cookie(response)
    return TokenResponse(access_token=token, role=admin.role, org_id=admin.org_id)


@router.get("/me", response_model=CurrentUserResponse)
def me(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> CurrentUserResponse:
    system_role = active_system_role(db, user)
    if system_role is not None:
        return CurrentUserResponse(
            id=user.id,
            org_id=user.org_id,
            email=user.email,
            role=user.role,
            effective_role=system_role.role,
            active_org_id=user.org_id,
            is_system_admin=True,
            capabilities=capabilities_for_user(db, user),
        )
    membership = active_membership(db, user)
    legacy_role = "admin" if membership.role == "org_admin" else "proctor"
    return CurrentUserResponse(
        id=user.id,
        org_id=membership.org_id,
        email=user.email,
        role=legacy_role,
        effective_role=system_role.role if system_role else membership.role,
        active_org_id=membership.org_id,
        is_system_admin=system_role is not None,
        capabilities=capabilities_for_user(db, user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    clear_auth_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def setup_mfa(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> MfaSetupResponse:
    secret = generate_secret()
    recovery_codes, recovery_hashes = generate_recovery_codes()
    user.mfa_secret_encrypted = encrypt_secret(secret)
    user.mfa_recovery_codes_json = recovery_hashes
    user.mfa_enabled = False
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    uri = provisioning_uri(secret, user.email)
    return MfaSetupResponse(
        secret=secret,
        provisioning_uri=uri,
        qr_code_data_url=qr_code_data_url(uri),
        recovery_codes=recovery_codes,
    )


@router.post("/mfa/confirm", response_model=TokenResponse)
def confirm_mfa(
    payload: MfaConfirmRequest,
    response: Response,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> TokenResponse:
    if not user.mfa_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chua khoi tao MFA")
    if not verify_totp(decrypt_secret(user.mfa_secret_encrypted), payload.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ma MFA khong hop le")
    user.mfa_enabled = True
    user.session_version += 1
    user.updated_at = datetime.now(timezone.utc)
    system_roles = db.query(models.SystemRole).filter_by(
        user_id=user.id,
        role="system_admin",
        status="pending_mfa",
    ).all()
    for system_role in system_roles:
        system_role.status = "active"
        system_role.updated_at = datetime.now(timezone.utc)
    db.commit()
    active_org_id = getattr(user, "_authorization_org_id", user.org_id)
    membership = db.query(models.OrganizationMembership).filter_by(
        user_id=user.id,
        org_id=active_org_id,
    ).one()
    legacy_role = "admin" if membership.role == "org_admin" else "proctor"
    token = create_access_token(user.id, legacy_role, active_org_id, user.session_version)
    set_auth_cookie(response, token)
    has_active_system_role = db.query(models.SystemRole.id).filter_by(
        user_id=user.id,
        role="system_admin",
        status="active",
    ).first() is not None
    effective_role = "system_admin" if has_active_system_role else legacy_role
    return TokenResponse(access_token=token, role=effective_role, org_id=active_org_id)


@router.get("/organizations", response_model=list[MyOrganizationResponse])
def my_organizations(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[MyOrganizationResponse]:
    rows = (
        db.query(models.OrganizationMembership, models.Organization)
        .join(models.Organization, models.Organization.id == models.OrganizationMembership.org_id)
        .filter(models.OrganizationMembership.user_id == user.id)
        .order_by(models.Organization.name.asc())
        .all()
    )
    return [
        MyOrganizationResponse(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            role=membership.role,
            membership_status=membership.status,
        )
        for membership, organization in rows
    ]


@router.post("/switch-organization/{org_id}", response_model=TokenResponse)
def switch_organization(
    org_id: str,
    response: Response,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> TokenResponse:
    membership = db.query(models.OrganizationMembership).filter_by(
        user_id=user.id,
        org_id=org_id,
        status="active",
    ).first()
    organization = db.get(models.Organization, org_id)
    if membership is None or organization is None or organization.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay to chuc")
    if membership.expires_at is not None:
        expires_at = membership.expires_at.replace(
            tzinfo=membership.expires_at.tzinfo or timezone.utc,
        )
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Quyen da het han")
    legacy_role = "admin" if membership.role == "org_admin" else "proctor"
    token = create_access_token(user.id, legacy_role, org_id, user.session_version)
    set_auth_cookie(response, token)
    return TokenResponse(access_token=token, role=legacy_role, org_id=org_id)


@router.post(
    "/invitations/accept",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def accept_invitation(
    payload: AcceptInvitationRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    enforce_rate_limit(
        request,
        "invitation-accept-ip",
        limit=PUBLIC_IP_LIMIT_PER_MINUTE,
        window_sec=60.0,
    )
    token_hash = hashlib.sha256(payload.invitation_token.encode("utf-8")).hexdigest()
    invitation = db.query(models.Invitation).filter_by(
        token_hash=token_hash,
        status="pending",
    ).first()
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loi moi khong hop le")
    expires_at = invitation.expires_at.replace(
        tzinfo=invitation.expires_at.tzinfo or timezone.utc,
    )
    if expires_at <= datetime.now(timezone.utc):
        invitation.status = "expired"
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Loi moi da het han")

    user = db.query(models.User).filter_by(email=invitation.email).first()
    if user is None:
        legacy_role = "admin" if invitation.role == "org_admin" else "proctor"
        user = models.User(
            org_id=invitation.org_id,
            email=invitation.email,
            password_hash=hash_password(payload.password),
            role=legacy_role,
            status="active",
        )
        db.add(user)
        db.flush()
    elif not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai mat khau")

    membership = db.query(models.OrganizationMembership).filter_by(
        user_id=user.id,
        org_id=invitation.org_id,
    ).first()
    if membership is None:
        membership = models.OrganizationMembership(
            user_id=user.id,
            org_id=invitation.org_id,
            role=invitation.role,
            status="active",
            invited_by_user_id=invitation.invited_by_user_id,
        )
        db.add(membership)
    else:
        membership.role = invitation.role
        membership.status = "active"
        membership.updated_at = datetime.now(timezone.utc)

    invitation.status = "accepted"
    invitation.accepted_by_user_id = user.id
    invitation.accepted_at = datetime.now(timezone.utc)
    record_audit(
        db,
        actor=user,
        action="org.invitation.accept",
        resource_type="invitation",
        resource_id=invitation.id,
        org_id=invitation.org_id,
        request=request,
        after={"email": invitation.email, "role": invitation.role},
    )
    db.commit()
    db.refresh(user)

    legacy_role = "admin" if invitation.role == "org_admin" else "proctor"
    token = create_access_token(
        user.id,
        legacy_role,
        invitation.org_id,
        user.session_version,
    )
    set_auth_cookie(response, token)
    return TokenResponse(
        access_token=token,
        role=legacy_role,
        org_id=invitation.org_id,
    )


@router.post("/proctors", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_proctor(
    payload: CreateProctorRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_permission(Permission.ORG_MEMBERS_MANAGE)),
) -> models.User:
    """Chi admin tao duoc tai khoan proctor, luon gan vao dung org cua chinh
    admin do (khong nhan org_id tu client) - day la diem cach ly multi-tenant
    quan trong nhat cua endpoint nay."""
    admin_membership = active_membership(db, admin)
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email da duoc dang ky")

    proctor = models.User(
        org_id=admin_membership.org_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="proctor",
    )
    db.add(proctor)
    db.flush()
    db.add(
        models.OrganizationMembership(
            user_id=proctor.id,
            org_id=admin_membership.org_id,
            role="exam_manager",
            status="active",
            invited_by_user_id=admin.id,
        )
    )
    db.commit()
    db.refresh(proctor)
    return proctor
