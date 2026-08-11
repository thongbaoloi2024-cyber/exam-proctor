"""System-admin APIs. System roles are provisioned only by the bootstrap CLI."""
from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import models
from ..audit import enrich_audit_actor_identity, record_audit
from ..authorization import Permission, require_system_permission
from ..db import get_db
from ..policies import PlatformPolicy, get_platform_policy
from ..session_materializer import SESSIONS_ROOT

router = APIRouter(prefix="/system", tags=["system"])


class SystemOverviewResponse(BaseModel):
    organizations: int
    active_organizations: int
    users: int
    exams: int
    active_sessions: int
    pending_access_grants: int


class OperationsCenterResponse(BaseModel):
    database_status: str
    database_latency_ms: float
    redis_status: str
    report_jobs: dict[str, int]
    evidence_storage_bytes: int
    sessions_connected: int
    extension_versions: dict[str, int]
    recent_report_failures: int
    checked_at: datetime


class PlatformPolicyResponse(BaseModel):
    policy: PlatformPolicy
    version: int
    updated_at: datetime | None
    updated_by_user_id: str | None


class UpdatePlatformPolicyRequest(BaseModel):
    policy: PlatformPolicy
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=500)


class SystemOrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str | None
    status: str
    quota_concurrent_sessions: int | None
    retention_days: int
    created_at: datetime
    updated_at: datetime


class ChartPoint(BaseModel):
    label: str
    value: int


class ChartCategory(BaseModel):
    key: str
    label: str
    value: int


class RankedOrganization(BaseModel):
    id: str
    name: str
    value: int


class SystemOverviewAnalyticsResponse(BaseModel):
    days: int
    totals: SystemOverviewResponse
    deltas: dict[str, int]
    session_trend: list[ChartPoint]
    organization_status: list[ChartCategory]
    exam_status: list[ChartCategory]
    top_organizations: list[RankedOrganization]


class SystemOrganizationDirectoryItem(SystemOrganizationResponse):
    user_count: int
    org_admin_count: int
    exam_count: int
    active_session_count: int


class SystemOrganizationPageResponse(BaseModel):
    items: list[SystemOrganizationDirectoryItem]
    total: int
    page: int
    page_size: int
    pages: int


class OrganizationAdminSummary(BaseModel):
    user_id: str
    email: str
    status: str


class SystemOrganizationDetailResponse(BaseModel):
    organization: SystemOrganizationDirectoryItem
    administrators: list[OrganizationAdminSummary]
    session_trend: list[ChartPoint]
    recent_audit: list["AuditLogResponse"]


class CreateSystemOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    admin_email: str = Field(min_length=3, max_length=255)
    retention_days: int = Field(default=365, ge=1, le=3650)
    quota_concurrent_sessions: int | None = Field(default=None, ge=1, le=1_000_000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("Ten to chuc khong hop le")
        return value

    @field_validator("admin_email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if "@" not in value:
            raise ValueError("Email khong hop le")
        return value


class CreatedSystemOrganizationResponse(BaseModel):
    organization: SystemOrganizationResponse
    admin_invitation_token: str
    invitation_expires_at: datetime


class CreateOrganizationAdminInvitationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    expires_in_hours: int = Field(default=72, ge=1, le=336)

    @field_validator("email")
    @classmethod
    def normalize_admin_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if "@" not in value:
            raise ValueError("Email khong hop le")
        return value


class CreatedOrganizationAdminInvitationResponse(BaseModel):
    id: str
    email: str
    status: str
    expires_at: datetime
    invitation_token: str


class UpdateSystemOrganizationRequest(BaseModel):
    status: Literal["active", "suspended"] | None = None
    quota_concurrent_sessions: int | None = Field(default=None, ge=1, le=1_000_000)
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    reason: str = Field(min_length=3, max_length=500)


class AccessGrantRequest(BaseModel):
    org_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=10, max_length=500)
    scope: Literal["evidence.read"] = "evidence.read"
    requested_duration_minutes: int = Field(default=30, ge=5, le=240)


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
    decision_reason: str | None = None
    created_at: datetime
    approved_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None


class AccessGrantDirectoryItem(AccessGrantResponse):
    organization_name: str
    requester_email: str
    effective_status: str


class AccessGrantPageResponse(BaseModel):
    items: list[AccessGrantDirectoryItem]
    total: int
    page: int
    page_size: int
    pages: int


class SystemSecurityAnalyticsResponse(BaseModel):
    days: int
    status_totals: list[ChartCategory]
    request_trend: list[ChartPoint]
    security_events: list[ChartCategory]


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_user_id: str | None
    actor_display_name: str | None = None
    actor_email: str | None = None
    actor_role: str | None
    org_id: str | None
    exam_id: str | None
    access_grant_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    reason: str | None
    request_id: str | None
    created_at: datetime


class AuditLogDetailResponse(AuditLogResponse):
    ip_address: str | None
    before_json: str | None
    after_json: str | None


class AuditLogPageResponse(BaseModel):
    items: list[AuditLogDetailResponse]
    total: int
    page: int
    page_size: int
    pages: int


class SystemAuditAnalyticsResponse(BaseModel):
    days: int
    activity_trend: list[ChartPoint]
    action_categories: list[ChartCategory]
    outcomes: list[ChartCategory]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _day_start(days: int) -> datetime:
    now = _now()
    today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return today - timedelta(days=days - 1)


def _trend(rows: list[datetime], days: int) -> list[ChartPoint]:
    start = _day_start(days)
    counts = Counter(_as_utc(value).date().isoformat() for value in rows if _as_utc(value) >= start)
    return [
        ChartPoint(label=(start + timedelta(days=index)).date().isoformat(), value=counts.get(
            (start + timedelta(days=index)).date().isoformat(), 0,
        ))
        for index in range(days)
    ]


def _organization_stat_maps(
    db: Session,
    organization_ids: list[str],
) -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    if not organization_ids:
        return {}, {}, {}, {}
    user_counts = dict(
        db.query(models.User.org_id, func.count(models.User.id))
        .filter(models.User.org_id.in_(organization_ids))
        .group_by(models.User.org_id)
        .all()
    )
    admin_counts = dict(
        db.query(models.OrganizationMembership.org_id, func.count(models.OrganizationMembership.id))
        .filter(
            models.OrganizationMembership.org_id.in_(organization_ids),
            models.OrganizationMembership.role == "org_admin",
            models.OrganizationMembership.status == "active",
        )
        .group_by(models.OrganizationMembership.org_id)
        .all()
    )
    exam_counts = dict(
        db.query(models.Exam.org_id, func.count(models.Exam.id))
        .filter(models.Exam.org_id.in_(organization_ids))
        .group_by(models.Exam.org_id)
        .all()
    )
    session_counts = dict(
        db.query(models.Exam.org_id, func.count(models.ExamSession.id))
        .join(models.ExamSession, models.ExamSession.exam_id == models.Exam.id)
        .filter(
            models.Exam.org_id.in_(organization_ids),
            models.ExamSession.status.in_(["pending", "active", "disconnected"]),
        )
        .group_by(models.Exam.org_id)
        .all()
    )
    return user_counts, admin_counts, exam_counts, session_counts


def _organization_item(
    organization: models.Organization,
    stat_maps: tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]],
) -> SystemOrganizationDirectoryItem:
    user_counts, admin_counts, exam_counts, session_counts = stat_maps
    base = SystemOrganizationResponse.model_validate(organization).model_dump()
    return SystemOrganizationDirectoryItem(
        **base,
        user_count=user_counts.get(organization.id, 0),
        org_admin_count=admin_counts.get(organization.id, 0),
        exam_count=exam_counts.get(organization.id, 0),
        active_session_count=session_counts.get(organization.id, 0),
    )


def _effective_grant_status(grant: models.AccessGrant) -> str:
    if grant.status in {"pending", "active"} and _as_utc(grant.expires_at) <= _now():
        return "expired"
    return grant.status


@router.get("/overview", response_model=SystemOverviewResponse)
def overview(
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_system_permission(Permission.SYSTEM_ORGANIZATIONS_READ)),
) -> SystemOverviewResponse:
    customer_organizations = db.query(models.Organization).filter(or_(
        models.Organization.slug.is_(None),
        models.Organization.slug != "system",
    ))
    return SystemOverviewResponse(
        organizations=customer_organizations.count(),
        active_organizations=customer_organizations.filter(
            models.Organization.status == "active",
        ).count(),
        users=db.query(func.count(models.User.id)).scalar() or 0,
        exams=db.query(func.count(models.Exam.id)).scalar() or 0,
        active_sessions=db.query(func.count(models.ExamSession.id)).filter(
            models.ExamSession.status.in_(["pending", "active", "disconnected"]),
        ).scalar() or 0,
        pending_access_grants=db.query(func.count(models.AccessGrant.id)).filter(
            models.AccessGrant.status == "pending",
            models.AccessGrant.expires_at > _now(),
        ).scalar() or 0,
    )


@router.get("/operations", response_model=OperationsCenterResponse)
def operations_center(
    db: Session = Depends(get_db),
    _actor: models.User = Depends(require_system_permission(Permission.SYSTEM_SECURITY_READ)),
) -> OperationsCenterResponse:
    started = time.perf_counter()
    db.query(models.Organization.id).limit(1).all()
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    job_rows = db.query(models.ReportJob.status, func.count(models.ReportJob.id)).group_by(models.ReportJob.status).all()
    version_rows = (
        db.query(models.ExamSession.extension_version, func.count(models.ExamSession.id))
        .filter(models.ExamSession.extension_version.is_not(None))
        .group_by(models.ExamSession.extension_version)
        .all()
    )
    storage_bytes = 0
    try:
        root = SESSIONS_ROOT.resolve()
        if root.is_dir():
            storage_bytes = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
    except OSError:
        storage_bytes = -1
    recent_cutoff = _now() - timedelta(hours=24)
    return OperationsCenterResponse(
        database_status="healthy",
        database_latency_ms=latency_ms,
        redis_status="configured" if os.environ.get("REDIS_URL", "").strip() else "not_configured",
        report_jobs={str(key): int(value) for key, value in job_rows},
        evidence_storage_bytes=storage_bytes,
        sessions_connected=db.query(models.ExamSession).filter_by(status="active").count(),
        extension_versions={str(key): int(value) for key, value in version_rows},
        recent_report_failures=db.query(models.ReportJob).filter(
            models.ReportJob.status == "failed",
            models.ReportJob.created_at >= recent_cutoff,
        ).count(),
        checked_at=_now(),
    )


@router.get("/policy", response_model=PlatformPolicyResponse)
def get_system_policy(
    db: Session = Depends(get_db),
    _actor: models.User = Depends(require_system_permission(Permission.SYSTEM_SECURITY_READ)),
) -> PlatformPolicyResponse:
    stored = db.get(models.PlatformPolicySetting, "default")
    return PlatformPolicyResponse(
        policy=get_platform_policy(db),
        version=stored.version if stored else 0,
        updated_at=stored.updated_at if stored else None,
        updated_by_user_id=stored.updated_by_user_id if stored else None,
    )


@router.put("/policy", response_model=PlatformPolicyResponse)
def update_system_policy(
    payload: UpdatePlatformPolicyRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_system_permission(Permission.SYSTEM_ORGANIZATIONS_MANAGE)),
) -> PlatformPolicyResponse:
    stored = db.get(models.PlatformPolicySetting, "default")
    current_version = stored.version if stored else 0
    if payload.expected_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Chinh sach da duoc cap nhat", "current_version": current_version},
        )
    before = get_platform_policy(db).model_dump()
    if stored is None:
        stored = models.PlatformPolicySetting(id="default", version=1)
        db.add(stored)
    else:
        stored.version += 1
    stored.settings_json = json.dumps(payload.policy.model_dump(), sort_keys=True)
    stored.updated_by_user_id = actor.id
    stored.updated_at = _now()
    record_audit(
        db,
        actor=actor,
        action="system.policy.update",
        resource_type="platform_policy",
        resource_id="default",
        reason=payload.reason,
        request=request,
        before=before,
        after=payload.policy.model_dump(),
    )
    db.commit()
    db.refresh(stored)
    return PlatformPolicyResponse(
        policy=payload.policy,
        version=stored.version,
        updated_at=stored.updated_at,
        updated_by_user_id=stored.updated_by_user_id,
    )


@router.get("/analytics/overview", response_model=SystemOverviewAnalyticsResponse)
def overview_analytics(
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_system_permission(Permission.SYSTEM_ORGANIZATIONS_READ)),
) -> SystemOverviewAnalyticsResponse:
    current_start = _day_start(days)
    previous_start = current_start - timedelta(days=days)
    totals = overview(db=db, _user=_user)

    def period_delta(model, column) -> int:
        current_count = db.query(func.count(model.id)).filter(column >= current_start).scalar() or 0
        previous_count = db.query(func.count(model.id)).filter(
            column >= previous_start,
            column < current_start,
        ).scalar() or 0
        return current_count - previous_count

    session_dates = [row[0] for row in db.query(models.ExamSession.started_at).filter(
        models.ExamSession.started_at >= current_start,
    ).all()]
    organization_status_counts = Counter(row[0] for row in db.query(
        models.Organization.status,
    ).filter(or_(
        models.Organization.slug.is_(None),
        models.Organization.slug != "system",
    )).all())
    exam_status_counts = Counter(row[0] for row in db.query(models.Exam.status).all())
    organizations = db.query(models.Organization).filter(or_(
        models.Organization.slug.is_(None),
        models.Organization.slug != "system",
    )).all()
    stats = _organization_stat_maps(db, [organization.id for organization in organizations])
    active_session_counts = stats[3]
    ranked = sorted(
        (
            RankedOrganization(
                id=organization.id,
                name=organization.name,
                value=active_session_counts.get(organization.id, 0),
            )
            for organization in organizations
        ),
        key=lambda item: (-item.value, item.name.casefold()),
    )[:6]
    return SystemOverviewAnalyticsResponse(
        days=days,
        totals=totals,
        deltas={
            "organizations": period_delta(models.Organization, models.Organization.created_at),
            "users": period_delta(models.User, models.User.created_at),
            "exams": period_delta(models.Exam, models.Exam.created_at),
            "sessions": period_delta(models.ExamSession, models.ExamSession.started_at),
        },
        session_trend=_trend(session_dates, days),
        organization_status=[
            ChartCategory(key=key, label={"active": "Hoạt động", "suspended": "Tạm khóa"}.get(key, key), value=value)
            for key, value in sorted(organization_status_counts.items())
        ],
        exam_status=[
            ChartCategory(
                key=key,
                label={
                    "draft": "Bản nháp",
                    "scheduled": "Đã lên lịch",
                    "open": "Đang mở",
                    "closed": "Đã đóng",
                    "archived": "Lưu trữ",
                }.get(key, key),
                value=value,
            )
            for key, value in sorted(exam_status_counts.items())
        ],
        top_organizations=ranked,
    )


@router.get("/organizations", response_model=list[SystemOrganizationResponse])
def list_organizations(
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_system_permission(Permission.SYSTEM_ORGANIZATIONS_READ)),
) -> list[models.Organization]:
    return db.query(models.Organization).filter(or_(
        models.Organization.slug.is_(None),
        models.Organization.slug != "system",
    )).order_by(models.Organization.created_at.desc()).all()


@router.get("/organizations/page", response_model=SystemOrganizationPageResponse)
def page_organizations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=5, le=100),
    search: str = Query(default="", max_length=100),
    organization_status: Literal["active", "suspended"] | None = Query(default=None, alias="status"),
    sort: Literal["created_desc", "created_asc", "name_asc", "name_desc"] = "created_desc",
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_system_permission(Permission.SYSTEM_ORGANIZATIONS_READ)),
) -> SystemOrganizationPageResponse:
    query = db.query(models.Organization).filter(or_(
        models.Organization.slug.is_(None),
        models.Organization.slug != "system",
    ))
    normalized_search = search.strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        query = query.filter(or_(
            models.Organization.name.ilike(pattern),
            models.Organization.slug.ilike(pattern),
        ))
    if organization_status:
        query = query.filter(models.Organization.status == organization_status)
    total = query.count()
    order_by = {
        "created_desc": models.Organization.created_at.desc(),
        "created_asc": models.Organization.created_at.asc(),
        "name_asc": models.Organization.name.asc(),
        "name_desc": models.Organization.name.desc(),
    }[sort]
    organizations = query.order_by(order_by).offset((page - 1) * page_size).limit(page_size).all()
    stats = _organization_stat_maps(db, [organization.id for organization in organizations])
    return SystemOrganizationPageResponse(
        items=[_organization_item(organization, stats) for organization in organizations],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/organizations/{org_id}", response_model=SystemOrganizationDetailResponse)
def get_organization_detail(
    org_id: str,
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_system_permission(Permission.SYSTEM_ORGANIZATIONS_READ)),
) -> SystemOrganizationDetailResponse:
    organization = db.get(models.Organization, org_id)
    if organization is None or organization.slug == "system":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay to chuc")
    stats = _organization_stat_maps(db, [organization.id])
    administrators = (
        db.query(models.User, models.OrganizationMembership)
        .join(
            models.OrganizationMembership,
            models.OrganizationMembership.user_id == models.User.id,
        )
        .filter(
            models.OrganizationMembership.org_id == organization.id,
            models.OrganizationMembership.role == "org_admin",
        )
        .order_by(models.User.email.asc())
        .all()
    )
    session_dates = [row[0] for row in (
        db.query(models.ExamSession.started_at)
        .join(models.Exam, models.Exam.id == models.ExamSession.exam_id)
        .filter(
            models.Exam.org_id == organization.id,
            models.ExamSession.started_at >= _day_start(days),
        )
        .all()
    )]
    audit_entries = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.org_id == organization.id)
        .order_by(models.AuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    return SystemOrganizationDetailResponse(
        organization=_organization_item(organization, stats),
        administrators=[
            OrganizationAdminSummary(
                user_id=user.id,
                email=user.email,
                status=membership.status,
            )
            for user, membership in administrators
        ],
        session_trend=_trend(session_dates, days),
        recent_audit=[AuditLogResponse.model_validate(entry) for entry in audit_entries],
    )


@router.post(
    "/organizations",
    response_model=CreatedSystemOrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    payload: CreateSystemOrganizationRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_system_permission(Permission.SYSTEM_ORGANIZATIONS_MANAGE)),
) -> CreatedSystemOrganizationResponse:
    organization = models.Organization(
        name=payload.name,
        status="active",
        retention_days=payload.retention_days,
        quota_concurrent_sessions=payload.quota_concurrent_sessions,
    )
    db.add(organization)
    db.flush()
    organization.slug = f"org-{organization.id.replace('-', '')[:12]}"
    raw_token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(hours=72)
    invitation = models.Invitation(
        org_id=organization.id,
        email=payload.admin_email,
        role="org_admin",
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        status="pending",
        invited_by_user_id=actor.id,
        expires_at=expires_at,
    )
    db.add(invitation)
    record_audit(
        db,
        actor=actor,
        action="system.organization.create",
        resource_type="organization",
        resource_id=organization.id,
        org_id=organization.id,
        request=request,
        after={"name": organization.name, "admin_email": payload.admin_email},
    )
    db.commit()
    db.refresh(organization)
    return CreatedSystemOrganizationResponse(
        organization=SystemOrganizationResponse.model_validate(organization),
        admin_invitation_token=raw_token,
        invitation_expires_at=expires_at,
    )


@router.patch("/organizations/{org_id}", response_model=SystemOrganizationResponse)
def update_organization(
    org_id: str,
    payload: UpdateSystemOrganizationRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_system_permission(Permission.SYSTEM_ORGANIZATIONS_MANAGE)),
) -> models.Organization:
    organization = db.get(models.Organization, org_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay to chuc")
    if organization.slug == "system":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Khong the thay doi tenant noi bo cua he thong",
        )
    before = {
        "status": organization.status,
        "quota_concurrent_sessions": organization.quota_concurrent_sessions,
        "retention_days": organization.retention_days,
    }
    if payload.status is not None:
        organization.status = payload.status
    if "quota_concurrent_sessions" in payload.model_fields_set:
        organization.quota_concurrent_sessions = payload.quota_concurrent_sessions
    if payload.retention_days is not None:
        organization.retention_days = payload.retention_days
    organization.updated_at = _now()
    if organization.status == "suspended":
        affected_users = (
            db.query(models.User)
            .join(
                models.OrganizationMembership,
                models.OrganizationMembership.user_id == models.User.id,
            )
            .filter(models.OrganizationMembership.org_id == organization.id)
            .all()
        )
        for user in affected_users:
            user.session_version += 1
    record_audit(
        db,
        actor=actor,
        action="system.organization.update",
        resource_type="organization",
        resource_id=organization.id,
        org_id=organization.id,
        reason=payload.reason,
        request=request,
        before=before,
        after={
            "status": organization.status,
            "quota_concurrent_sessions": organization.quota_concurrent_sessions,
            "retention_days": organization.retention_days,
        },
    )
    db.commit()
    db.refresh(organization)
    return organization


@router.post(
    "/organizations/{org_id}/admin-invitations",
    response_model=CreatedOrganizationAdminInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_organization_admin(
    org_id: str,
    payload: CreateOrganizationAdminInvitationRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_system_permission(Permission.SYSTEM_ORGANIZATIONS_MANAGE)),
) -> CreatedOrganizationAdminInvitationResponse:
    organization = db.get(models.Organization, org_id)
    if organization is None or organization.slug == "system":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay to chuc")
    existing_user = db.query(models.User).filter_by(email=payload.email).first()
    if existing_user and db.query(models.OrganizationMembership).filter_by(
        org_id=org_id,
        user_id=existing_user.id,
    ).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email da la thanh vien")
    pending = db.query(models.Invitation).filter_by(
        org_id=org_id,
        email=payload.email,
        status="pending",
    ).first()
    if pending and _as_utc(pending.expires_at) > _now():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Loi moi dang con hieu luc")
    raw_token = secrets.token_urlsafe(32)
    invitation = models.Invitation(
        org_id=org_id,
        email=payload.email,
        role="org_admin",
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        status="pending",
        invited_by_user_id=actor.id,
        expires_at=_now() + timedelta(hours=payload.expires_in_hours),
    )
    db.add(invitation)
    db.flush()
    record_audit(
        db,
        actor=actor,
        action="system.organization.admin.invite",
        resource_type="invitation",
        resource_id=invitation.id,
        org_id=org_id,
        request=request,
        after={"email": payload.email, "role": "org_admin"},
    )
    db.commit()
    db.refresh(invitation)
    return CreatedOrganizationAdminInvitationResponse(
        id=invitation.id,
        email=invitation.email,
        status=invitation.status,
        expires_at=invitation.expires_at,
        invitation_token=raw_token,
    )


@router.post(
    "/access-grants",
    response_model=AccessGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_access_grant(
    payload: AccessGrantRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_system_permission(Permission.SYSTEM_BREAK_GLASS)),
) -> models.AccessGrant:
    organization = db.get(models.Organization, payload.org_id)
    if organization is None or organization.status != "active" or organization.slug == "system":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay to chuc")
    grant = models.AccessGrant(
        requester_user_id=actor.id,
        org_id=organization.id,
        reason=payload.reason,
        scope=payload.scope,
        status="pending",
        read_only=True,
        expires_at=_now() + timedelta(minutes=payload.requested_duration_minutes),
    )
    db.add(grant)
    db.flush()
    record_audit(
        db,
        actor=actor,
        action="system.break_glass.request",
        resource_type="access_grant",
        resource_id=grant.id,
        org_id=organization.id,
        reason=payload.reason,
        request=request,
        after={"scope": grant.scope, "expires_at": grant.expires_at},
    )
    db.commit()
    db.refresh(grant)
    return grant


@router.get("/access-grants", response_model=AccessGrantPageResponse)
def page_access_grants(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=5, le=100),
    grant_status: Literal["pending", "active", "expired", "revoked"] | None = Query(
        default=None,
        alias="status",
    ),
    organization_id: str | None = Query(default=None, alias="org_id", max_length=36),
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_system_permission(Permission.SYSTEM_SECURITY_READ)),
) -> AccessGrantPageResponse:
    query = (
        db.query(models.AccessGrant, models.Organization, models.User)
        .join(models.Organization, models.Organization.id == models.AccessGrant.org_id)
        .join(models.User, models.User.id == models.AccessGrant.requester_user_id)
    )
    if organization_id:
        query = query.filter(models.AccessGrant.org_id == organization_id)
    if grant_status == "expired":
        query = query.filter(
            models.AccessGrant.status.in_(["pending", "active"]),
            models.AccessGrant.expires_at <= _now(),
        )
    elif grant_status:
        query = query.filter(models.AccessGrant.status == grant_status)
        if grant_status in {"pending", "active"}:
            query = query.filter(models.AccessGrant.expires_at > _now())
    total = query.count()
    rows = (
        query.order_by(models.AccessGrant.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AccessGrantPageResponse(
        items=[
            AccessGrantDirectoryItem(
                **AccessGrantResponse.model_validate(grant).model_dump(),
                organization_name=organization.name,
                requester_email=requester.email,
                effective_status=_effective_grant_status(grant),
            )
            for grant, organization, requester in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/analytics/security", response_model=SystemSecurityAnalyticsResponse)
def security_analytics(
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_system_permission(Permission.SYSTEM_SECURITY_READ)),
) -> SystemSecurityAnalyticsResponse:
    grants = db.query(models.AccessGrant).all()
    status_counts = Counter(_effective_grant_status(grant) for grant in grants)
    labels = {
        "pending": "Chờ duyệt",
        "active": "Đang hiệu lực",
        "expired": "Hết hạn",
        "revoked": "Đã thu hồi",
    }
    ordered_statuses = ["pending", "active", "expired", "revoked"]
    security_rows = db.query(models.AuditLog.action, func.count(models.AuditLog.id)).filter(
        models.AuditLog.action.like("security.%"),
        models.AuditLog.created_at >= _day_start(days),
    ).group_by(models.AuditLog.action).all()
    return SystemSecurityAnalyticsResponse(
        days=days,
        status_totals=[
            ChartCategory(key=key, label=labels[key], value=status_counts.get(key, 0))
            for key in ordered_statuses
        ],
        request_trend=_trend([grant.created_at for grant in grants], days),
        security_events=[
            ChartCategory(key=action, label={
                "security.login.failed": "Đăng nhập thất bại",
                "security.login.success": "Đăng nhập thành công",
                "security.mfa.failed": "MFA thất bại",
                "security.mfa.success": "MFA thành công",
            }.get(action, action), value=count)
            for action, count in security_rows
        ],
    )


@router.get("/analytics/audit", response_model=SystemAuditAnalyticsResponse)
def audit_analytics(
    days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_system_permission(Permission.SYSTEM_SECURITY_READ)),
) -> SystemAuditAnalyticsResponse:
    entries = db.query(models.AuditLog).filter(
        models.AuditLog.created_at >= _day_start(days),
    ).all()
    category_counts: Counter[str] = Counter()
    for entry in entries:
        parts = entry.action.split(".")
        category_counts[parts[1] if len(parts) > 1 else parts[0]] += 1
    outcome_counts = Counter(entry.outcome for entry in entries)
    category_labels = {
        "profile": "Hồ sơ",
        "member": "Thành viên",
        "invitation": "Lời mời",
        "policy": "Chính sách",
        "break_glass": "Quyền truy cập ngoại lệ",
        "organization": "Tổ chức",
        "login": "Đăng nhập",
        "mfa": "Xác minh MFA",
        "password": "Mật khẩu",
        "create": "Tạo kỳ thi",
        "update": "Cập nhật kỳ thi",
        "assignment": "Phân công kỳ thi",
        "status": "Trạng thái kỳ thi",
        "join_code": "Mã tham gia",
        "session": "Phiên thi",
        "evidence": "Dữ liệu giám sát",
        "incident": "Sự cố",
        "report": "Báo cáo",
    }
    return SystemAuditAnalyticsResponse(
        days=days,
        activity_trend=_trend([entry.created_at for entry in entries], days),
        action_categories=[
            ChartCategory(key=key, label=category_labels.get(key, key), value=value)
            for key, value in category_counts.most_common(8)
        ],
        outcomes=[
            ChartCategory(
                key=key,
                label={"success": "Thành công", "failed": "Thất bại", "denied": "Bị từ chối"}.get(key, key),
                value=value,
            )
            for key, value in sorted(outcome_counts.items())
        ],
    )


@router.get("/audit/page", response_model=AuditLogPageResponse)
def page_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=10, le=100),
    days: int = Query(default=30, ge=1, le=365),
    search: str = Query(default="", max_length=100),
    outcome: str | None = Query(default=None, max_length=20),
    org_id: str | None = Query(default=None, max_length=36),
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_system_permission(Permission.SYSTEM_SECURITY_READ)),
) -> AuditLogPageResponse:
    query = (
        db.query(models.AuditLog)
        .outerjoin(models.User, models.AuditLog.actor_user_id == models.User.id)
        .filter(models.AuditLog.created_at >= _day_start(days))
    )
    normalized_search = search.strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        query = query.filter(or_(
            models.AuditLog.action.ilike(pattern),
            models.AuditLog.resource_type.ilike(pattern),
            models.AuditLog.resource_id.ilike(pattern),
            models.AuditLog.request_id.ilike(pattern),
            models.User.display_name.ilike(pattern),
            models.User.email.ilike(pattern),
        ))
    if outcome:
        query = query.filter(models.AuditLog.outcome == outcome)
    if org_id:
        query = query.filter(models.AuditLog.org_id == org_id)
    total = query.count()
    entries = (
        query.order_by(models.AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    enrich_audit_actor_identity(db, entries)
    return AuditLogPageResponse(
        items=[AuditLogDetailResponse.model_validate(entry) for entry in entries],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/audit", response_model=list[AuditLogResponse])
def list_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_system_permission(Permission.SYSTEM_SECURITY_READ)),
) -> list[models.AuditLog]:
    safe_limit = min(max(limit, 1), 500)
    entries = (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .limit(safe_limit)
        .all()
    )
    return enrich_audit_actor_identity(db, entries)


SystemOrganizationDetailResponse.model_rebuild()
