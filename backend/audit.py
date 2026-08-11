"""Append-only security and administration activity-log helpers."""
from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from . import models

_REDACTED_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "invitation_token",
    "session_token",
    "snapshot_base64",
    "embedding",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.casefold() in _REDACTED_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


def _json(value: Any | None) -> str | None:
    if value is None:
        return None
    return json.dumps(_redact(value), ensure_ascii=False, sort_keys=True, default=str)


def enrich_audit_actor_identity(
    db: Session,
    entries: list[models.AuditLog],
) -> list[models.AuditLog]:
    """Attach display-safe actor fields to a batch of activity-log rows.

    Activity-log rows retain the immutable user ID while the directory remains the
    source of truth for the current display name and email. Loading all actors
    in one query avoids an extra query for every row in a paged response.
    """
    actor_ids = {entry.actor_user_id for entry in entries if entry.actor_user_id}
    actors = {
        user.id: user
        for user in db.query(models.User).filter(models.User.id.in_(actor_ids)).all()
    } if actor_ids else {}
    for entry in entries:
        actor = actors.get(entry.actor_user_id)
        entry.actor_display_name = actor.display_name if actor else None
        entry.actor_email = actor.email if actor else None
    return entries


def record_audit(
    db: Session,
    *,
    actor: models.User | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    org_id: str | None = None,
    exam_id: str | None = None,
    access_grant_id: str | None = None,
    outcome: str = "success",
    reason: str | None = None,
    request: Request | None = None,
    before: Any | None = None,
    after: Any | None = None,
) -> models.AuditLog:
    entry = models.AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        org_id=org_id,
        exam_id=exam_id,
        access_grant_id=access_grant_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        reason=reason,
        request_id=getattr(request.state, "request_id", None) if request else None,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent")[:500] if request else None,
        before_json=_json(before),
        after_json=_json(after),
    )
    db.add(entry)
    return entry
