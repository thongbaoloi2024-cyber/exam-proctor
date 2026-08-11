"""Central RBAC + tenant/resource scope authorization.

Authentication answers *who* the caller is. This module answers *what* that
identity may do and *which* organization/exam/session it may do it to. Routers
must not recreate these rules with ad-hoc role checks.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Query, Session

from . import models
from .auth import get_current_user
from .db import get_db


class Permission(StrEnum):
    SYSTEM_ORGANIZATIONS_READ = "system.organizations.read"
    SYSTEM_ORGANIZATIONS_MANAGE = "system.organizations.manage"
    SYSTEM_SECURITY_READ = "system.security.read"
    SYSTEM_BREAK_GLASS = "system.break_glass"
    ORG_MEMBERS_READ = "org.members.read"
    ORG_MEMBERS_MANAGE = "org.members.manage"
    ORG_POLICY_MANAGE = "org.policy.manage"
    ORG_AUDIT_READ = "org.audit.read"
    EXAM_CREATE = "exam.create"
    EXAM_READ = "exam.read"
    EXAM_MANAGE = "exam.manage"
    EXAM_ASSIGN = "exam.assign"
    EXAM_MONITOR = "exam.monitor"
    EXAM_SESSIONS_END = "exam.sessions.end"
    EXAM_EVIDENCE_READ = "exam.evidence.read"
    EXAM_INCIDENT_REVIEW = "exam.incident.review"
    EXAM_REPORTS_EXPORT = "exam.reports.export"


_ORG_ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    # Organization administrators govern the tenant boundary only. Exam
    # operations are deliberately separated and belong to exam managers.
    "org_admin": frozenset(
        {
            Permission.ORG_MEMBERS_READ,
            Permission.ORG_MEMBERS_MANAGE,
            Permission.ORG_POLICY_MANAGE,
            Permission.ORG_AUDIT_READ,
        }
    ),
    # An exam manager may create an exam and becomes its owner. Every other
    # exam capability is resolved from ExamAssignment.
    "exam_manager": frozenset({Permission.EXAM_CREATE}),
}

_ASSIGNMENT_ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "owner": frozenset(
        {
            Permission.EXAM_READ,
            Permission.EXAM_MANAGE,
            Permission.EXAM_ASSIGN,
            Permission.EXAM_MONITOR,
            Permission.EXAM_SESSIONS_END,
            Permission.EXAM_EVIDENCE_READ,
            Permission.EXAM_INCIDENT_REVIEW,
            Permission.EXAM_REPORTS_EXPORT,
        }
    ),
    "manager": frozenset(
        {
            Permission.EXAM_READ,
            Permission.EXAM_MANAGE,
            Permission.EXAM_ASSIGN,
            Permission.EXAM_MONITOR,
            Permission.EXAM_SESSIONS_END,
            Permission.EXAM_EVIDENCE_READ,
            Permission.EXAM_INCIDENT_REVIEW,
            Permission.EXAM_REPORTS_EXPORT,
        }
    ),
    "proctor": frozenset(
        {
            Permission.EXAM_READ,
            Permission.EXAM_MONITOR,
            Permission.EXAM_SESSIONS_END,
            Permission.EXAM_EVIDENCE_READ,
            Permission.EXAM_INCIDENT_REVIEW,
            Permission.EXAM_REPORTS_EXPORT,
        }
    ),
}

_SYSTEM_ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "system_admin": frozenset(
        {
            Permission.SYSTEM_ORGANIZATIONS_READ,
            Permission.SYSTEM_ORGANIZATIONS_MANAGE,
            Permission.SYSTEM_SECURITY_READ,
            Permission.SYSTEM_BREAK_GLASS,
        }
    ),
}

_BREAK_GLASS_READ_PERMISSIONS = frozenset(
    {
        Permission.EXAM_READ,
        Permission.EXAM_MONITOR,
        Permission.EXAM_EVIDENCE_READ,
        Permission.EXAM_REPORTS_EXPORT,
    }
)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _not_found(resource_label: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Khong tim thay {resource_label}",
    )


def _forbidden() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Khong du quyen")


def active_membership(
    db: Session,
    user: models.User,
    org_id: str | None = None,
) -> models.OrganizationMembership:
    """Return the active membership for the requested tenant.

    Active organization selection is introduced in the organization-management
    phase. During compatibility, ``User.org_id`` remains the server-owned active
    tenant and request payloads cannot override it.
    """

    if user.status != "active":
        raise _forbidden()
    target_org_id = org_id or getattr(user, "_authorization_org_id", user.org_id)
    organization = db.get(models.Organization, target_org_id)
    if organization is None or organization.status != "active":
        raise _not_found("to chuc")
    membership = db.query(models.OrganizationMembership).filter_by(
        user_id=user.id,
        org_id=target_org_id,
        status="active",
    ).first()
    if membership is None:
        raise _forbidden()
    if membership.expires_at is not None and _as_utc(membership.expires_at) <= datetime.now(timezone.utc):
        raise _forbidden()
    return membership


def require_permission(permission: Permission) -> Callable:
    """FastAPI dependency for organization-level capabilities."""

    def _dependency(
        db: Session = Depends(get_db),
        user: models.User = Depends(get_current_user),
    ) -> models.User:
        membership = active_membership(db, user)
        if permission not in _ORG_ROLE_PERMISSIONS.get(membership.role, frozenset()):
            raise _forbidden()
        return user

    return _dependency


def active_system_role(db: Session, user: models.User) -> models.SystemRole | None:
    if user.status != "active" or not user.mfa_enabled:
        return None
    return db.query(models.SystemRole).filter_by(
        user_id=user.id,
        role="system_admin",
        status="active",
    ).first()


def _active_break_glass_grants(db: Session, user: models.User) -> Query:
    now = datetime.now(timezone.utc)
    return db.query(models.AccessGrant).filter(
        models.AccessGrant.requester_user_id == user.id,
        models.AccessGrant.scope == "evidence.read",
        models.AccessGrant.status == "active",
        models.AccessGrant.read_only.is_(True),
        models.AccessGrant.expires_at > now,
        models.AccessGrant.revoked_at.is_(None),
    )


def capabilities_for_user(db: Session, user: models.User) -> list[str]:
    capabilities: set[Permission] = set()
    system_role = active_system_role(db, user)
    if system_role is not None:
        capabilities.update(_SYSTEM_ROLE_PERMISSIONS.get(system_role.role, frozenset()))
        if _active_break_glass_grants(db, user).first() is not None:
            capabilities.update(_BREAK_GLASS_READ_PERMISSIONS)
        # A System Admin is never treated as a tenant administrator. Resource
        # access is added only by an active, read-only break-glass grant.
        return sorted(permission.value for permission in capabilities)
    try:
        membership = active_membership(db, user)
    except HTTPException:
        membership = None
    if membership is not None:
        capabilities.update(_ORG_ROLE_PERMISSIONS.get(membership.role, frozenset()))
        # An org_admin must not recover exam access from stale or accidental
        # assignments. Only exam_manager memberships can activate them.
        if membership.role == "exam_manager":
            assignments = db.query(models.ExamAssignment.assignment_role).filter_by(
                user_id=user.id,
                status="active",
            ).distinct().all()
            for (assignment_role,) in assignments:
                capabilities.update(
                    _ASSIGNMENT_ROLE_PERMISSIONS.get(assignment_role, frozenset())
                )
    return sorted(permission.value for permission in capabilities)


def exam_access_for_user(
    db: Session,
    user: models.User,
    exam: models.Exam,
) -> tuple[str | None, frozenset[Permission]]:
    """Return the caller's assignment role and effective permissions for one exam.

    Account-level capabilities are useful for building the primary navigation,
    but they are deliberately a union across every active assignment.  Resource
    actions must use this helper so being a manager on one exam never makes a
    proctor-only exam look manageable in the UI.
    """

    if active_system_role(db, user) is not None:
        grant = _active_break_glass_grants(db, user).filter(
            models.AccessGrant.org_id == exam.org_id,
        ).first()
        return (None, _BREAK_GLASS_READ_PERMISSIONS if grant is not None else frozenset())

    membership = active_membership(db, user)
    if membership.org_id != exam.org_id:
        return (None, frozenset())

    permissions = _ORG_ROLE_PERMISSIONS.get(membership.role, frozenset())
    if membership.role != "exam_manager":
        return (None, permissions)

    assignment = db.query(models.ExamAssignment).filter_by(
        exam_id=exam.id,
        user_id=user.id,
        status="active",
    ).first()
    if assignment is None:
        return (None, permissions)
    if assignment.expires_at is not None and _as_utc(
        assignment.expires_at,
    ) <= datetime.now(timezone.utc):
        return (None, permissions)
    return (
        assignment.assignment_role,
        permissions
        | _ASSIGNMENT_ROLE_PERMISSIONS.get(assignment.assignment_role, frozenset()),
    )


def require_system_permission(permission: Permission) -> Callable:
    def _dependency(
        db: Session = Depends(get_db),
        user: models.User = Depends(get_current_user),
    ) -> models.User:
        system_role = active_system_role(db, user)
        if system_role is None or permission not in _SYSTEM_ROLE_PERMISSIONS.get(
            system_role.role,
            frozenset(),
        ):
            raise _forbidden()
        return user

    return _dependency


def _valid_break_glass_grant(
    db: Session,
    user: models.User,
    org_id: str,
    permission: Permission,
) -> bool:
    if active_system_role(db, user) is None:
        return False
    # Break-glass is deliberately read-only. It never permits lifecycle,
    # assignment, session-end or incident-review mutations.
    if permission not in _BREAK_GLASS_READ_PERMISSIONS:
        return False
    grant = _active_break_glass_grants(db, user).filter(
        models.AccessGrant.org_id == org_id,
    ).first()
    return grant is not None


def active_break_glass_grant(
    db: Session,
    user: models.User,
    org_id: str,
) -> models.AccessGrant | None:
    """Return the active grant used for sensitive-read audit attribution."""

    if active_system_role(db, user) is None:
        return None
    return _active_break_glass_grants(db, user).filter(
        models.AccessGrant.org_id == org_id,
    ).first()


def scoped_exam_query(
    db: Session,
    user: models.User,
    permission: Permission = Permission.EXAM_READ,
) -> Query:
    """Return an Exam query already restricted to the caller's resource scope."""

    if active_system_role(db, user) is not None:
        if permission not in _BREAK_GLASS_READ_PERMISSIONS:
            return db.query(models.Exam).filter(models.Exam.id == "__not_authorized__")
        granted_org_ids = _active_break_glass_grants(db, user).with_entities(
            models.AccessGrant.org_id,
        )
        return db.query(models.Exam).filter(models.Exam.org_id.in_(granted_org_ids))

    membership = active_membership(db, user)
    if permission in _ORG_ROLE_PERMISSIONS.get(membership.role, frozenset()):
        return db.query(models.Exam).filter(models.Exam.org_id == membership.org_id)
    if membership.role != "exam_manager":
        return db.query(models.Exam).filter(models.Exam.id == "__not_authorized__")
    allowed_assignment_roles = [
        role
        for role, permissions in _ASSIGNMENT_ROLE_PERMISSIONS.items()
        if permission in permissions
    ]
    if not allowed_assignment_roles:
        return db.query(models.Exam).filter(models.Exam.id == "__not_authorized__")
    now = datetime.now(timezone.utc)
    return (
        db.query(models.Exam)
        .join(models.ExamAssignment, models.ExamAssignment.exam_id == models.Exam.id)
        .filter(
            models.Exam.org_id == membership.org_id,
            models.ExamAssignment.user_id == user.id,
            models.ExamAssignment.status == "active",
            models.ExamAssignment.assignment_role.in_(allowed_assignment_roles),
            (
                models.ExamAssignment.expires_at.is_(None)
                | (models.ExamAssignment.expires_at > now)
            ),
        )
    )


def authorize_exam(
    db: Session,
    user: models.User,
    exam_id: str,
    permission: Permission,
) -> models.Exam:
    if active_system_role(db, user) is not None:
        exam = db.get(models.Exam, exam_id)
        if exam is None:
            raise _not_found("ky thi")
        if _valid_break_glass_grant(db, user, exam.org_id, permission):
            return exam
        raise _forbidden()
    membership = active_membership(db, user)
    exam = db.query(models.Exam).filter(
        models.Exam.id == exam_id,
        models.Exam.org_id == membership.org_id,
    ).first()
    if exam is None:
        raise _not_found("ky thi")
    if permission in _ORG_ROLE_PERMISSIONS.get(membership.role, frozenset()):
        return exam
    if membership.role != "exam_manager":
        raise _forbidden()

    assignment = db.query(models.ExamAssignment).filter_by(
        exam_id=exam.id,
        user_id=user.id,
        status="active",
    ).first()
    if assignment is None:
        # Do not disclose that an in-tenant but unassigned exam exists.
        raise _not_found("ky thi")
    if assignment.expires_at is not None and _as_utc(assignment.expires_at) <= datetime.now(timezone.utc):
        raise _not_found("ky thi")
    if permission not in _ASSIGNMENT_ROLE_PERMISSIONS.get(
        assignment.assignment_role,
        frozenset(),
    ):
        raise _forbidden()
    return exam


def authorize_session(
    db: Session,
    user: models.User,
    session_id: str,
    permission: Permission,
) -> models.ExamSession:
    if active_system_role(db, user) is not None:
        exam_session = db.get(models.ExamSession, session_id)
        if exam_session is None:
            raise _not_found("phien")
        authorize_exam(db, user, exam_session.exam_id, permission)
        return exam_session
    membership = active_membership(db, user)
    exam_session = (
        db.query(models.ExamSession)
        .join(models.Exam, models.Exam.id == models.ExamSession.exam_id)
        .filter(
            models.ExamSession.id == session_id,
            models.Exam.org_id == membership.org_id,
        )
        .first()
    )
    if exam_session is None:
        raise _not_found("phien")
    authorize_exam(db, user, exam_session.exam_id, permission)
    return exam_session
