"""Organization administration, memberships, invitations and policy."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from .. import models
from ..audit import record_audit
from ..authorization import Permission, active_membership, require_permission
from ..db import get_db

router = APIRouter(prefix="/organizations/current", tags=["organizations"])


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str | None
    status: str
    quota_concurrent_sessions: int | None
    retention_days: int
    created_at: datetime
    updated_at: datetime


class UpdateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized or any(ord(char) < 32 for char in normalized):
            raise ValueError("Ten to chuc khong hop le")
        return normalized


class MemberResponse(BaseModel):
    user_id: str
    email: str
    user_status: str
    role: str
    membership_status: str
    expires_at: datetime | None
    created_at: datetime


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


class OrganizationPolicy(BaseModel):
    default_candidate_auth_mode: Literal["manual", "google"] = "manual"
    min_extension_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
    require_extension: bool = False
    require_fullscreen: bool = True
    require_camera: bool = True
    require_microphone: bool = False
    require_screen_share: bool = False
    block_clipboard: bool = True
    max_focus_loss_seconds: float = Field(default=5.0, ge=0.0, le=300.0)
    retention_days: int = Field(default=365, ge=1, le=3650)


class AccessGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    requester_user_id: str
    org_id: str
    reason: str
    scope: str
    status: str
    read_only: bool
    approved_by_user_id: str | None
    created_at: datetime
    approved_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None


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


def _member_response(membership: models.OrganizationMembership, user: models.User) -> MemberResponse:
    return MemberResponse(
        user_id=user.id,
        email=user.email,
        user_status=user.status,
        role=membership.role,
        membership_status=membership.status,
        expires_at=membership.expires_at,
        created_at=membership.created_at,
    )


@router.get("", response_model=OrganizationResponse)
def get_current_organization(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_MEMBERS_READ)),
) -> models.Organization:
    return _current_org(db, user)


@router.patch("", response_model=OrganizationResponse)
def update_current_organization(
    payload: UpdateOrganizationRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_POLICY_MANAGE)),
) -> models.Organization:
    organization = _current_org(db, user)
    before = {"name": organization.name}
    organization.name = payload.name
    organization.updated_at = _now()
    record_audit(
        db,
        actor=user,
        action="org.profile.update",
        resource_type="organization",
        resource_id=organization.id,
        org_id=organization.id,
        request=request,
        before=before,
        after={"name": organization.name},
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
    try:
        stored = json.loads(organization.settings_json or "{}")
    except (TypeError, ValueError):
        stored = {}
    stored.setdefault("retention_days", organization.retention_days)
    return OrganizationPolicy.model_validate(stored)


@router.put("/policy", response_model=OrganizationPolicy)
def update_policy(
    payload: OrganizationPolicy,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_POLICY_MANAGE)),
) -> OrganizationPolicy:
    organization = _current_org(db, user)
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
) -> list[models.AccessGrant]:
    membership = active_membership(db, user)
    return (
        db.query(models.AccessGrant)
        .filter(models.AccessGrant.org_id == membership.org_id)
        .order_by(models.AccessGrant.created_at.desc())
        .all()
    )


@router.post("/access-grants/{grant_id}/approve", response_model=AccessGrantResponse)
def approve_access_grant(
    grant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission(Permission.ORG_MEMBERS_MANAGE)),
) -> models.AccessGrant:
    membership = active_membership(db, actor)
    grant = db.query(models.AccessGrant).filter_by(
        id=grant_id,
        org_id=membership.org_id,
    ).first()
    if grant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay yeu cau")
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
    record_audit(
        db,
        actor=actor,
        action="org.break_glass.approve",
        resource_type="access_grant",
        resource_id=grant.id,
        org_id=membership.org_id,
        reason=grant.reason,
        request=request,
        after={"scope": grant.scope, "expires_at": grant.expires_at, "read_only": True},
    )
    db.commit()
    db.refresh(grant)
    return grant


@router.post("/access-grants/{grant_id}/revoke", response_model=AccessGrantResponse)
def revoke_access_grant(
    grant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_permission(Permission.ORG_MEMBERS_MANAGE)),
) -> models.AccessGrant:
    membership = active_membership(db, actor)
    grant = db.query(models.AccessGrant).filter_by(
        id=grant_id,
        org_id=membership.org_id,
    ).first()
    if grant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay yeu cau")
    grant.status = "revoked"
    grant.revoked_at = _now()
    record_audit(
        db,
        actor=actor,
        action="org.break_glass.revoke",
        resource_type="access_grant",
        resource_id=grant.id,
        org_id=membership.org_id,
        request=request,
    )
    db.commit()
    db.refresh(grant)
    return grant


@router.get("/audit", response_model=list[AuditLogResponse])
def list_organization_audit(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_permission(Permission.ORG_AUDIT_READ)),
) -> list[models.AuditLog]:
    membership = active_membership(db, user)
    safe_limit = min(max(limit, 1), 500)
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.org_id == membership.org_id)
        .order_by(models.AuditLog.created_at.desc())
        .limit(safe_limit)
        .all()
    )
