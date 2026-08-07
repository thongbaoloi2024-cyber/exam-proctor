"""Dang ky (tao Organization + admin dau tien) va dang nhap cho admin/proctor.
Hoc sinh khong dung router nay - xem exams.py:join_exam.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from .. import models
from ..auth import (
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    set_auth_cookie,
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
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)

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
    if user is None or user.status != "active" or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai email hoac mat khau")
    system_role = db.query(models.SystemRole).filter_by(
        user_id=user.id,
        role="system_admin",
    ).first()
    is_system_identity = system_role is not None and system_role.status in {
        "active",
        "pending_mfa",
    }
    organization = db.get(models.Organization, user.org_id)
    if (organization is None or organization.status != "active") and not is_system_identity:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="To chuc dang bi khoa")

    mfa_reenrollment_required = False
    if user.mfa_enabled:
        if not payload.mfa_code:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Can ma MFA")
        submitted_code = payload.mfa_code.strip()
        recovery_verified, remaining = consume_recovery_code(
            user.mfa_recovery_codes_json,
            submitted_code,
        )
        if recovery_verified:
            # Recovery hashes do not depend on the encryption key. If the
            # encrypted TOTP secret can no longer be opened, consume the code
            # and force a clean enrollment instead of returning a server error.
            secret_readable = False
            if user.mfa_secret_encrypted:
                try:
                    decrypt_secret(user.mfa_secret_encrypted)
                    secret_readable = True
                except ValueError:
                    secret_readable = False
            if secret_readable:
                user.mfa_recovery_codes_json = remaining
                db.commit()
            else:
                user.mfa_enabled = False
                user.mfa_secret_encrypted = None
                user.mfa_recovery_codes_json = None
                user.session_version += 1
                user.updated_at = datetime.now(timezone.utc)
                if system_role is not None and system_role.status == "active":
                    system_role.status = "pending_mfa"
                    system_role.updated_at = datetime.now(timezone.utc)
                mfa_reenrollment_required = True
                db.commit()
        else:
            if not user.mfa_secret_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cau hinh MFA khong con hop le; can reset MFA",
                )
            try:
                secret = decrypt_secret(user.mfa_secret_encrypted)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Khong giai ma duoc MFA secret; hay dung recovery code hoac reset MFA",
                ) from exc
            if not verify_totp(secret, submitted_code):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ma MFA khong hop le")

    # Recover records produced by older bootstrap versions: a user who has
    # already passed MFA must not remain stuck in pending_mfa forever.
    if system_role is not None and system_role.status == "pending_mfa" and user.mfa_enabled:
        system_role.status = "active"
        system_role.updated_at = datetime.now(timezone.utc)
        db.commit()

    token = create_access_token(user.id, user.role, user.org_id, user.session_version)
    set_auth_cookie(response, token)
    return TokenResponse(
        access_token=token,
        role="system_admin" if system_role is not None and system_role.status == "active" else user.role,
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
