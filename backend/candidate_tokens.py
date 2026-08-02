"""Opaque, revocable candidate-device tokens used by the browser extension."""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from . import models


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_device_id(device_id: str) -> str:
    return _hash(device_id.strip())


def candidate_token_ttl_days() -> int:
    try:
        value = int(os.environ.get("CANDIDATE_TOKEN_TTL_DAYS", "90"))
    except ValueError:
        return 90
    return min(max(value, 1), 365)


def bearer_token_from_request(request: Request) -> Optional[str]:
    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not value.strip():
        return None
    return value.strip()


def issue_candidate_device_token(
    db: Session,
    candidate: models.CandidateIdentity,
    device_id: str,
) -> tuple[str, models.CandidateDevice]:
    now = _now()
    device_hash = hash_device_id(device_id)
    for existing in (
        db.query(models.CandidateDevice)
        .filter(
            models.CandidateDevice.candidate_identity_id == candidate.id,
            models.CandidateDevice.device_id_hash == device_hash,
            models.CandidateDevice.revoked_at.is_(None),
        )
        .all()
    ):
        existing.revoked_at = now

    raw_token = secrets.token_urlsafe(48)
    device = models.CandidateDevice(
        candidate_identity_id=candidate.id,
        device_id_hash=device_hash,
        token_hash=_hash(raw_token),
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=candidate_token_ttl_days()),
    )
    db.add(device)
    return raw_token, device


def resolve_candidate_token(
    db: Session,
    raw_token: Optional[str],
    *,
    touch: bool = True,
) -> tuple[models.CandidateIdentity, models.CandidateDevice]:
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Danh tinh thi sinh da het han hoac khong hop le",
    )
    if not raw_token or len(raw_token) > 512:
        raise error
    device = (
        db.query(models.CandidateDevice)
        .filter(models.CandidateDevice.token_hash == _hash(raw_token))
        .first()
    )
    now = _now()
    if (
        device is None
        or device.revoked_at is not None
        or _as_utc(device.expires_at) <= now
    ):
        raise error
    candidate = db.get(models.CandidateIdentity, device.candidate_identity_id)
    if candidate is None or not candidate.email_verified:
        raise error
    if touch:
        device.last_used_at = now
    return candidate, device


def revoke_candidate_token(db: Session, raw_token: Optional[str]) -> None:
    _, device = resolve_candidate_token(db, raw_token, touch=False)
    device.revoked_at = _now()
