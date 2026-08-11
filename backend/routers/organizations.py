"""Organization administration, memberships, invitations and policy."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from ..audit import record_audit
from ..auth import verify_password
from ..authorization import Permission, active_membership, require_permission
from ..db import get_db
from ..mfa import decrypt_secret, verify_totp
from ..policies import (
    OrganizationPolicy,
    get_effective_organization_policy,
    get_platform_policy,
    validate_organization_policy,
)
from ..rate_limit import enforce_rate_limit

router = APIRouter(prefix="/organizations/current", tags=["organizations"])


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    logo_url: str | None
    address: str | None
    email: str | None
    phone: str | None
    website: str | None
    slug: str | None
    status: str
    quota_concurrent_sessions: int | None
    retention_days: int
    created_at: datetime
    updated_at: datetime


class UpdateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    logo_url: str | None = Field(default=None, max_length=2048)
    address: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    website: str | None = Field(default=None, max_length=2048)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized or any(ord(char) < 32 for char in normalized):
            raise ValueError("Ten to chuc khong hop le")
        return normalized

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = " ".join(value.strip().split())
        if any(ord(char) < 32 for char in normalized):
            raise ValueError("Dia chi khong hop le")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().casefold()
        local_part, separator, domain = normalized.rpartition("@")
        if (
            not separator
            or not local_part
            or not domain
            or "@" in local_part
            or any(char.isspace() for char in normalized)
            or domain.startswith(".")
            or domain.endswith(".")
        ):
            raise ValueError("Email to chuc khong hop le")
        return normalized

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = " ".join(value.strip().split())
        if (
            len(normalized) < 7
            or not all(char.isdigit() or char in "+-(). " for char in normalized)
        ):
            raise ValueError("So dien thoai khong hop le")
        return normalized

    @field_validator("logo_url")
    @classmethod
    def normalize_logo_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or any(ord(char) < 32 for char in normalized)
        ):
            raise ValueError("URL logo phai la URL HTTPS hop le")
        return normalized

    @field_validator("website")
    @classmethod
    def normalize_website(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or any(ord(char) < 32 for char in normalized)
        ):
            raise ValueError("Website khong hop le")
        return normalized


class MemberResponse(BaseModel):
    user_id: str
    email: str
    user_status: str
    role: str
    membership_status: str
    expires_at: datetime | None
    created_at: datetime
    mfa_enabled: bool


class OrganizationOverviewResponse(BaseModel):
    members_total: int
    members_active: int
    members_suspended: int
    members_with_mfa: int
    pending_invitations: int
    exams_total: int
    sessions_active: int
    concurrent_session_quota: int | None
    retention_days: int
    exam_status: dict[str, int]
    session_status: dict[str, int]
    quota_usage_percent: float | None


class UpdateMemberRequest(BaseModel):
    role: Literal["org_admin", "exam_manager"] | None = None
    status: Literal["active", "suspended", "revoked"] | None = None


class CreateInvitationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: Literal["org_admin", "exam_manager"]
    expires_in_hours: int = Field(default=72, ge=1, le=24 * 14)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if "@" not in value:
            raise ValueError("Email khong hop le")
        return value


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    status: str
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None


class CreatedInvitationResponse(InvitationResponse):
    invitation_token: str


class AccessGrantResponse(BaseModel):
    id: str
    requester_user_id: str
    requester_email: str
    org_id: str
    reason: str
    scope: str
    status: str
    read_only: bool
    approved_by_user_id: str | None
    decision_reason: str | None
    created_at: datetime
    approved_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None
    effective_status: str


class AccessGrantDecisionRequest(BaseModel):
    decision_reason: str = Field(min_length=3, max_length=500)
    verification_code: str = Field(min_length=1, max_length=128)

    @field_validator("decision_reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return " ".join(value.strip().split())


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    reason: str | None
    request_id: str | None
    created_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _current_org(db: Session, user: models.User) -> models.Organization:
    membership = active_membership(db, user)
    organization = db.get(models.Organization, membership.org_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay to chuc")
    return organization


def _effective_grant_status(grant: models.AccessGrant) -> str:
    expires_at = grant.expires_at.replace(tzinfo=grant.expires_at.tzinfo or timezone.utc)
    if grant.status in {"pending", "active"} and expires_at <= _now():
        return "expired"
    return grant.status


def _access_grant_response(
    grant: models.AccessGrant,
    requester: models.User,
) -> AccessGrantResponse:
    return AccessGrantResponse(
        id=grant.id,
        requester_user_id=grant.requester_user_id,
        requester_email=requester.email,
        org_id=grant.org_id,
        reason=grant.reason,
        scope=grant.scope,
        status=grant.status,
        read_only=grant.read_only,
        approved_by_user_id=grant.approved_by_user_id,
        decision_reason=grant.decision_reason,
        created_at=grant.created_at,
        approved_at=grant.approved_at,
        expires_at=grant.expires_at,
        revoked_at=grant.revoked_at,
        effective_status=_effective_grant_status(grant),
    )


def _verify_sensitive_action(
    actor: models.User,
    verification_code: str,
    request: Request,
) -> None:
    enforce_rate_limit(
        request,
        "sensitive-action",
        actor.id,
        limit=5,
        window_sec=300.0,
    )
    code = verification_code.strip()
    if actor.mfa_enabled:
        try:
            valid = bool(actor.mfa_secret_encrypted) and verify_totp(
                decrypt_secret(actor.mfa_secret_encrypted or ""),
                code,
            )
        except ValueError:
            valid = False
    elif actor.google_subject:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Tai khoan Google phai bat MFA truoc khi duyet quyen nhay cam",
        )
    else:
        valid = verify_password(code, actor.password_hash)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Xac thuc lai khong hop le",
        )


def _member_response(membership: models.OrganizationMembership, user: models.User) -> MemberResponse:
    return MemberResponse(
        user_id=user.id,
        email=user.email,
        user_status=user.status,
        role=membership.role,
        membership_status=membership.status,
        expires_at=membership.expires_at,
        created_at=membership.created_at,
        mfa_enabled=user.mfa_enabled,
    )


@router.get("", response_model=OrganizationResponse)
def get_current_organization(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_MEMBERS_READ)),
) -> models.Organization:
    return _current_org(db, user)


@router.get("/overview", response_model=OrganizationOverviewResponse)
def get_organization_overview(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_MEMBERS_READ)),
) -> OrganizationOverviewResponse:
    organization = _current_org(db, user)
    memberships = db.query(models.OrganizationMembership).filter_by(org_id=organization.id)
    member_rows = memberships.all()
    active_member_ids = [item.user_id for item in member_rows if item.status == "active"]
    mfa_count = (
        db.query(models.User).filter(
            models.User.id.in_(active_member_ids),
            models.User.mfa_enabled.is_(True),
        ).count()
        if active_member_ids else 0
    )
    exams = db.query(models.Exam).filter_by(org_id=organization.id).all()
    exam_ids = [exam.id for exam in exams]
    sessions = (
        db.query(models.ExamSession)
        .filter(models.ExamSession.exam_id.in_(exam_ids))
        .all()
        if exam_ids else []
    )
    active_sessions = sum(
        exam_session.status in {"pending", "active", "disconnected"}
        for exam_session in sessions
    )
    exam_status = {
        item: sum(exam.status == item for exam in exams)
        for item in ("draft", "scheduled", "open", "closed", "archived")
    }
    session_status = {
        item: sum(exam_session.status == item for exam_session in sessions)
        for item in ("pending", "active", "disconnected", "ended")
    }
    quota_usage_percent = (
        round(active_sessions / organization.quota_concurrent_sessions * 100, 1)
        if organization.quota_concurrent_sessions else None
    )
    return OrganizationOverviewResponse(
        members_total=len(member_rows),
        members_active=sum(item.status == "active" for item in member_rows),
        members_suspended=sum(item.status in {"suspended", "revoked"} for item in member_rows),
        members_with_mfa=mfa_count,
        pending_invitations=db.query(models.Invitation).filter_by(org_id=organization.id, status="pending").count(),
        exams_total=len(exams),
        sessions_active=active_sessions,
        concurrent_session_quota=organization.quota_concurrent_sessions,
        retention_days=organization.retention_days,
        exam_status=exam_status,
        session_status=session_status,
        quota_usage_percent=quota_usage_percent,
    )


@router.patch("", response_model=OrganizationResponse)
def update_current_organization(
    payload: UpdateOrganizationRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_POLICY_MANAGE)),
) -> models.Organization:
    organization = _current_org(db, user)
    before = {
        "name": organization.name,
        "logo_url": organization.logo_url,
        "address": organization.address,
        "email": organization.email,
        "phone": organization.phone,
        "website": organization.website,
    }
    organization.name = payload.name
    organization.logo_url = payload.logo_url
    organization.address = payload.address
    organization.email = payload.email
    organization.phone = payload.phone
    organization.website = payload.website
    organization.updated_at = _now()
    after = {
        "name": organization.name,
        "logo_url": organization.logo_url,
        "address": organization.address,
        "email": organization.email,
        "phone": organization.phone,
        "website": organization.website,
    }
    record_audit(
        db,
        actor=user,
        action="org.profile.update",
        resource_type="organization",
        resource_id=organization.id,
        org_id=organization.id,
        request=request,
        before=before,
        after=after,
    )
    db.commit()
    db.refresh(organization)
    return organization


@router.get("/members", response_model=list[MemberResponse])
def list_members(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_MEMBERS_READ)),
) -> list[MemberResponse]:
    membership = active_membership(db, user)
    rows = (
        db.query(models.OrganizationMembership, models.User)
        .join(models.User, models.User.id == models.OrganizationMembership.user_id)
        .filter(models.OrganizationMembership.org_id == membership.org_id)
        .order_by(models.User.email.asc())
        .all()
    )
    return [_member_response(item, member_user) for item, member_user in rows]


@router.patch("/members/{member_user_id}", response_model=MemberResponse)
def update_member(
    member_user_id: str,
    payload: UpdateMemberRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission(Permission.ORG_MEMBERS_MANAGE)),
) -> MemberResponse:
    actor_membership = active_membership(db, actor)
    membership = db.query(models.OrganizationMembership).filter_by(
        user_id=member_user_id,
        org_id=actor_membership.org_id,
    ).first()
    member_user = db.get(models.User, member_user_id)
    if membership is None or member_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay thanh vien")

    next_role = payload.role or membership.role
    next_status = payload.status or membership.status
    removing_active_admin = (
        membership.role == "org_admin"
        and membership.status == "active"
        and (next_role != "org_admin" or next_status != "active")
    )
    if removing_active_admin:
        active_admin_count = db.query(models.OrganizationMembership).filter_by(
            org_id=membership.org_id,
            role="org_admin",
            status="active",
        ).count()
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Khong the thu hoi Organization Admin cuoi cung",
            )

    before = {"role": membership.role, "status": membership.status}
    membership.role = next_role
    membership.status = next_status
    membership.updated_at = _now()
    member_user.session_version += 1
    member_user.updated_at = _now()
    if membership.org_id == member_user.org_id:
        member_user.role = "admin" if next_role == "org_admin" else "proctor"
        member_user.status = "active" if next_status == "active" else "suspended"
        member_user.locked_at = None if next_status == "active" else _now()
    record_audit(
        db,
        actor=actor,
        action="org.member.update",
        resource_type="organization_membership",
        resource_id=membership.id,
        org_id=membership.org_id,
        request=request,
        before=before,
        after={"role": membership.role, "status": membership.status},
    )
    db.commit()
    db.refresh(membership)
    db.refresh(member_user)
    return _member_response(membership, member_user)


@router.post(
    "/invitations",
    response_model=CreatedInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    payload: CreateInvitationRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission(Permission.ORG_MEMBERS_MANAGE)),
) -> CreatedInvitationResponse:
    membership = active_membership(db, actor)
    existing_user = db.query(models.User).filter_by(email=payload.email).first()
    if existing_user is not None:
        existing_membership = db.query(models.OrganizationMembership).filter_by(
            user_id=existing_user.id,
            org_id=membership.org_id,
        ).first()
        if existing_membership is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email da la thanh vien")
    pending = db.query(models.Invitation).filter_by(
        org_id=membership.org_id,
        email=payload.email,
        status="pending",
    ).first()
    if pending is not None and pending.expires_at.replace(
        tzinfo=pending.expires_at.tzinfo or timezone.utc,
    ) > _now():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Loi moi dang con hieu luc")

    raw_token = secrets.token_urlsafe(32)
    invitation = models.Invitation(
        org_id=membership.org_id,
        email=payload.email,
        role=payload.role,
        token_hash=_token_hash(raw_token),
        status="pending",
        invited_by_user_id=actor.id,
        expires_at=_now() + timedelta(hours=payload.expires_in_hours),
    )
    db.add(invitation)
    db.flush()
    record_audit(
        db,
        actor=actor,
        action="org.invitation.create",
        resource_type="invitation",
        resource_id=invitation.id,
        org_id=membership.org_id,
        request=request,
        after={"email": invitation.email, "role": invitation.role},
    )
    db.commit()
    db.refresh(invitation)
    return CreatedInvitationResponse(
        **InvitationResponse.model_validate(invitation).model_dump(),
        invitation_token=raw_token,
    )


@router.get("/invitations", response_model=list[InvitationResponse])
def list_invitations(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_MEMBERS_READ)),
) -> list[models.Invitation]:
    membership = active_membership(db, user)
    return (
        db.query(models.Invitation)
        .filter(models.Invitation.org_id == membership.org_id)
        .order_by(models.Invitation.created_at.desc())
        .all()
    )


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    invitation_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission(Permission.ORG_MEMBERS_MANAGE)),
) -> None:
    membership = active_membership(db, actor)
    invitation = db.query(models.Invitation).filter_by(
        id=invitation_id,
        org_id=membership.org_id,
    ).first()
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay loi moi")
    if invitation.status == "pending":
        invitation.status = "revoked"
        record_audit(
            db,
            actor=actor,
            action="org.invitation.revoke",
            resource_type="invitation",
            resource_id=invitation.id,
            org_id=membership.org_id,
            request=request,
        )
        db.commit()


@router.get("/policy", response_model=OrganizationPolicy)
def get_policy(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_MEMBERS_READ)),
) -> OrganizationPolicy:
    organization = _current_org(db, user)
    return get_effective_organization_policy(db, organization)


@router.put("/policy", response_model=OrganizationPolicy)
def update_policy(
    payload: OrganizationPolicy,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_POLICY_MANAGE)),
) -> OrganizationPolicy:
    organization = _current_org(db, user)
    try:
        validate_organization_policy(payload, get_platform_policy(db))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    before = organization.settings_json
    organization.settings_json = payload.model_dump_json()
    organization.retention_days = payload.retention_days
    organization.updated_at = _now()
    record_audit(
        db,
        actor=user,
        action="org.policy.update",
        resource_type="organization_policy",
        resource_id=organization.id,
        org_id=organization.id,
        request=request,
        before={"settings_json": before},
        after=payload.model_dump(),
    )
    db.commit()
    return payload


@router.get("/access-grants", response_model=list[AccessGrantResponse])
def list_access_grants(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_AUDIT_READ)),
) -> list[AccessGrantResponse]:
    membership = active_membership(db, user)
    rows = (
        db.query(models.AccessGrant, models.User)
        .join(models.User, models.User.id == models.AccessGrant.requester_user_id)
        .filter(models.AccessGrant.org_id == membership.org_id)
        .order_by(models.AccessGrant.created_at.desc())
        .all()
    )
    return [_access_grant_response(grant, requester) for grant, requester in rows]


@router.post("/access-grants/{grant_id}/approve", response_model=AccessGrantResponse)
def approve_access_grant(
    grant_id: str,
    payload: AccessGrantDecisionRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission(Permission.ORG_MEMBERS_MANAGE)),
) -> AccessGrantResponse:
    membership = active_membership(db, actor)
    row = (
        db.query(models.AccessGrant, models.User)
        .join(models.User, models.User.id == models.AccessGrant.requester_user_id)
        .filter(
            models.AccessGrant.id == grant_id,
            models.AccessGrant.org_id == membership.org_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay yeu cau")
    grant, requester = row
    _verify_sensitive_action(actor, payload.verification_code, request)
    if grant.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Yeu cau khong con cho duyet")
    expires_at = grant.expires_at.replace(tzinfo=grant.expires_at.tzinfo or timezone.utc)
    if expires_at <= _now():
        grant.status = "expired"
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Yeu cau da het han")
    grant.status = "active"
    grant.approved_by_user_id = actor.id
    grant.approved_at = _now()
    grant.decision_reason = payload.decision_reason
    record_audit(
        db,
        actor=actor,
        action="org.break_glass.approve",
        resource_type="access_grant",
        resource_id=grant.id,
        org_id=membership.org_id,
        reason=payload.decision_reason,
        request=request,
        after={"scope": grant.scope, "expires_at": grant.expires_at, "read_only": True},
    )
    db.commit()
    db.refresh(grant)
    return _access_grant_response(grant, requester)


@router.post("/access-grants/{grant_id}/revoke", response_model=AccessGrantResponse)
def revoke_access_grant(
    grant_id: str,
    payload: AccessGrantDecisionRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission(Permission.ORG_MEMBERS_MANAGE)),
) -> AccessGrantResponse:
    membership = active_membership(db, actor)
    row = (
        db.query(models.AccessGrant, models.User)
        .join(models.User, models.User.id == models.AccessGrant.requester_user_id)
        .filter(
            models.AccessGrant.id == grant_id,
            models.AccessGrant.org_id == membership.org_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay yeu cau")
    grant, requester = row
    _verify_sensitive_action(actor, payload.verification_code, request)
    grant.status = "revoked"
    grant.revoked_at = _now()
    grant.decision_reason = payload.decision_reason
    record_audit(
        db,
        actor=actor,
        action="org.break_glass.revoke",
        resource_type="access_grant",
        resource_id=grant.id,
        org_id=membership.org_id,
        reason=payload.decision_reason,
        request=request,
    )
    db.commit()
    db.refresh(grant)
    return _access_grant_response(grant, requester)


@router.get("/audit", response_model=list[AuditLogResponse])
def list_organization_audit(
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
    actor_user_id: str | None = None,
    outcome: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_AUDIT_READ)),
) -> list[models.AuditLog]:
    membership = active_membership(db, user)
    safe_limit = min(max(limit, 1), 500)
    query = db.query(models.AuditLog).filter(models.AuditLog.org_id == membership.org_id)
    if action:
        query = query.filter(models.AuditLog.action == action)
    if actor_user_id:
        query = query.filter(models.AuditLog.actor_user_id == actor_user_id)
    if outcome:
        query = query.filter(models.AuditLog.outcome == outcome)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(
            models.AuditLog.action.ilike(pattern),
            models.AuditLog.resource_type.ilike(pattern),
            models.AuditLog.resource_id.ilike(pattern),
            models.AuditLog.request_id.ilike(pattern),
        ))
    return query.order_by(models.AuditLog.created_at.desc()).offset(max(offset, 0)).limit(safe_limit).all()
