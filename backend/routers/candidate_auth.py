"""Google OIDC registration and reusable candidate-device authentication.

The browser extension never receives or stores a Google access/refresh token.
The backend exchanges the authorization code, verifies the ID token, then
issues its own opaque and revocable device token.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .. import models
from ..candidate_tokens import (
    bearer_token_from_request,
    issue_candidate_device_token,
    resolve_candidate_token,
    revoke_candidate_token,
)
from ..db import get_db
from ..rate_limit import LOGIN_ACCOUNT_LIMIT_PER_MINUTE, enforce_rate_limit

router = APIRouter(prefix="/candidate-auth", tags=["candidate-auth"])

_STATE_TTL_MINUTES = 10
_GRANT_TTL_SECONDS = 90


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class GoogleOAuthSettings:
    client_id: str
    client_secret: str
    callback_url: str
    extension_redirect_uris: frozenset[str]


def _google_settings() -> Optional[GoogleOAuthSettings]:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    callback_url = os.environ.get("GOOGLE_OAUTH_CALLBACK_URL", "").strip()
    redirect_uris = frozenset(
        item.strip()
        for item in os.environ.get("OAUTH_EXTENSION_REDIRECT_URIS", "").split(",")
        if item.strip()
    )
    if not any((client_id, client_secret, callback_url, redirect_uris)):
        return None
    if not all((client_id, client_secret, callback_url, redirect_uris)):
        raise RuntimeError(
            "Google OAuth can du GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, "
            "GOOGLE_OAUTH_CALLBACK_URL va OAUTH_EXTENSION_REDIRECT_URIS"
        )
    return GoogleOAuthSettings(client_id, client_secret, callback_url, redirect_uris)


def validate_google_oauth_configuration() -> None:
    settings = _google_settings()
    if settings is None:
        return
    callback = urlsplit(settings.callback_url)
    production = os.environ.get("APP_ENV", "development").strip().lower() == "production"
    if callback.scheme not in ({"https"} if production else {"http", "https"}) or not callback.netloc:
        raise RuntimeError("GOOGLE_OAUTH_CALLBACK_URL khong hop le")
    if production and any(urlsplit(uri).scheme != "https" for uri in settings.extension_redirect_uris):
        raise RuntimeError("OAUTH_EXTENSION_REDIRECT_URIS phai dung HTTPS trong production")


def _require_google_settings() -> GoogleOAuthSettings:
    settings = _google_settings()
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dang nhap Google chua duoc cau hinh tren backend",
        )
    return settings


def google_oauth_configured() -> bool:
    return _google_settings() is not None


def _append_redirect_query(uri: str, **params: str) -> str:
    parts = urlsplit(uri)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def _safe_claim_text(claims: dict[str, Any], key: str, maximum: int) -> Optional[str]:
    value = claims.get(key)
    if not isinstance(value, str):
        return None
    value = " ".join(value.strip().split())
    return value[:maximum] or None


def _exchange_and_verify_google(
    code: str,
    verifier: str,
    nonce: str,
    settings: GoogleOAuthSettings,
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
    token_body = response.json()
    raw_id_token = token_body.get("id_token")
    if not isinstance(raw_id_token, str):
        raise ValueError("Google khong tra ve id_token")

    # Lazy import keeps manual-only deployments lightweight at import time.
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


class CandidateProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    avatar_url: Optional[str]
    hosted_domain: Optional[str]


class CompleteGoogleLoginRequest(BaseModel):
    grant: str = Field(min_length=32, max_length=512)
    device_id: UUID


class CandidateLoginResponse(BaseModel):
    candidate_token: str
    token_expires_at: datetime
    profile: CandidateProfile


@router.get("/google/start")
def start_google_login(
    request: Request,
    extension_redirect_uri: str = Query(min_length=12, max_length=2048),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    enforce_rate_limit(
        request, "candidate-google-start", limit=LOGIN_ACCOUNT_LIMIT_PER_MINUTE, window_sec=60.0,
    )
    settings = _require_google_settings()
    if extension_redirect_uri not in settings.extension_redirect_uris:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Redirect cua extension khong duoc phep")

    now = _now()
    db.query(models.CandidateOAuthTransaction).filter(
        models.CandidateOAuthTransaction.expires_at < now,
    ).delete(synchronize_session=False)

    state_value = secrets.token_urlsafe(48)
    verifier = secrets.token_urlsafe(64)
    nonce = secrets.token_urlsafe(32)
    transaction = models.CandidateOAuthTransaction(
        state_hash=_sha256(state_value),
        extension_redirect_uri=extension_redirect_uri,
        pkce_verifier=verifier,
        oidc_nonce=nonce,
        created_at=now,
        expires_at=now + timedelta(minutes=_STATE_TTL_MINUTES),
    )
    db.add(transaction)
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
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}", status_code=302)


@router.get("/google/callback")
def google_callback(
    request: Request,
    state_value: str = Query(alias="state", min_length=16, max_length=512),
    code: Optional[str] = Query(default=None, min_length=1, max_length=4096),
    error: Optional[str] = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    enforce_rate_limit(
        request, "candidate-google-callback", limit=LOGIN_ACCOUNT_LIMIT_PER_MINUTE * 2, window_sec=60.0,
    )
    settings = _require_google_settings()
    transaction = (
        db.query(models.CandidateOAuthTransaction)
        .filter(models.CandidateOAuthTransaction.state_hash == _sha256(state_value))
        .first()
    )
    now = _now()
    if (
        transaction is None
        or transaction.completed_at is not None
        or _as_utc(transaction.expires_at) <= now
        or transaction.extension_redirect_uri not in settings.extension_redirect_uris
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state khong hop le hoac da het han")
    if error or not code:
        transaction.completed_at = now
        db.commit()
        return RedirectResponse(
            _append_redirect_query(transaction.extension_redirect_uri, error="google_login_cancelled"),
            status_code=302,
        )

    try:
        claims = _exchange_and_verify_google(
            code, transaction.pkce_verifier, transaction.oidc_nonce, settings,
        )
    except (httpx.HTTPError, ValueError, KeyError):
        transaction.completed_at = now
        db.commit()
        return RedirectResponse(
            _append_redirect_query(transaction.extension_redirect_uri, error="google_verification_failed"),
            status_code=302,
        )

    subject = _safe_claim_text(claims, "sub", 255)
    email = _safe_claim_text(claims, "email", 255)
    display_name = _safe_claim_text(claims, "name", 200) or email
    if not subject or not email or claims.get("email_verified") is not True:
        transaction.completed_at = now
        db.commit()
        return RedirectResponse(
            _append_redirect_query(transaction.extension_redirect_uri, error="google_email_not_verified"),
            status_code=302,
        )

    candidate = (
        db.query(models.CandidateIdentity)
        .filter(models.CandidateIdentity.provider_subject == subject)
        .first()
    )
    if candidate is None:
        candidate = models.CandidateIdentity(
            provider="google",
            provider_subject=subject,
            email=email.casefold(),
            email_verified=True,
            display_name=display_name,
        )
        db.add(candidate)
        db.flush()
    candidate.email = email.casefold()
    candidate.email_verified = True
    candidate.display_name = display_name
    candidate.avatar_url = _safe_claim_text(claims, "picture", 2048)
    candidate.hosted_domain = _safe_claim_text(claims, "hd", 255)
    candidate.updated_at = now
    candidate.last_login_at = now

    grant = secrets.token_urlsafe(48)
    transaction.completed_at = now
    transaction.candidate_identity_id = candidate.id
    transaction.grant_hash = _sha256(grant)
    transaction.grant_expires_at = now + timedelta(seconds=_GRANT_TTL_SECONDS)
    db.commit()
    return RedirectResponse(
        _append_redirect_query(transaction.extension_redirect_uri, grant=grant),
        status_code=302,
    )


@router.post("/google/complete", response_model=CandidateLoginResponse)
def complete_google_login(
    payload: CompleteGoogleLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> CandidateLoginResponse:
    enforce_rate_limit(
        request, "candidate-google-complete", limit=LOGIN_ACCOUNT_LIMIT_PER_MINUTE * 2, window_sec=60.0,
    )
    transaction = (
        db.query(models.CandidateOAuthTransaction)
        .filter(models.CandidateOAuthTransaction.grant_hash == _sha256(payload.grant))
        .first()
    )
    now = _now()
    if (
        transaction is None
        or transaction.candidate_identity_id is None
        or transaction.grant_used_at is not None
        or transaction.grant_expires_at is None
        or _as_utc(transaction.grant_expires_at) <= now
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Grant khong hop le hoac da het han")
    candidate = db.get(models.CandidateIdentity, transaction.candidate_identity_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Khong tim thay danh tinh thi sinh")

    transaction.grant_used_at = now
    raw_token, device = issue_candidate_device_token(db, candidate, str(payload.device_id))
    db.commit()
    db.refresh(device)
    return CandidateLoginResponse(
        candidate_token=raw_token,
        token_expires_at=device.expires_at,
        profile=CandidateProfile.model_validate(candidate),
    )


@router.get("/me", response_model=CandidateProfile)
def candidate_me(request: Request, db: Session = Depends(get_db)) -> CandidateProfile:
    candidate, _ = resolve_candidate_token(db, bearer_token_from_request(request))
    db.commit()
    return CandidateProfile.model_validate(candidate)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def candidate_logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Response:
    revoke_candidate_token(db, bearer_token_from_request(request))
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
