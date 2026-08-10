"""Google OAuth flows for dashboard users and organization registration."""
from __future__ import annotations

import os
from urllib.parse import parse_qs, urlsplit

from backend import models
from backend.db import SessionLocal
from backend.mfa import current_totp
from backend.routers import auth as auth_router

os.environ.setdefault(
    "GOOGLE_WEB_OAUTH_CALLBACK_URL",
    "https://backend.test/auth/google/callback",
)


def _oauth_state(location: str) -> str:
    return parse_qs(urlsplit(location).query)["state"][0]


def test_google_registration_requires_organization_completion(client, monkeypatch):
    monkeypatch.setattr(
        auth_router,
        "_exchange_and_verify_web_google",
        lambda *_args: {
            "sub": "google-register-subject",
            "email": "google-admin@test.local",
            "email_verified": True,
            "name": "Google Admin",
        },
    )
    started = client.get("/auth/google/start?flow=register", follow_redirects=False)
    assert started.status_code == 302
    assert "accounts.google.com" in started.headers["location"]

    callback = client.get(
        "/auth/google/callback",
        params={"state": _oauth_state(started.headers["location"]), "code": "verified-code"},
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert callback.headers["location"] == "/ui/register/organization"
    assert client.get("/auth/me").status_code == 401
    profile = client.get("/auth/google/registration")
    assert profile.status_code == 200
    assert profile.json()["email"] == "google-admin@test.local"

    completed = client.post(
        "/auth/google/register/complete",
        json={"organization_name": "Google Test Org"},
    )
    assert completed.status_code == 201
    assert completed.json()["role"] == "admin"
    assert client.get("/auth/me").status_code == 200
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="google-admin@test.local").one()
        assert user.google_subject == "google-register-subject"
        assert user.organization.name == "Google Test Org"


def test_google_login_links_verified_email_but_still_requires_mfa(client, monkeypatch):
    registered = client.post(
        "/auth/register",
        json={
            "organization_name": "Existing Google Org",
            "admin_email": "existing-google@test.local",
            "admin_password": "matkhau123",
        },
    )
    token = registered.json()["access_token"]
    setup = client.post(
        "/auth/mfa/setup",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    confirmed = client.post(
        "/auth/mfa/confirm",
        json={"code": current_totp(setup["secret"])},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert confirmed.status_code == 200

    monkeypatch.setattr(
        auth_router,
        "_exchange_and_verify_web_google",
        lambda *_args: {
            "sub": "existing-google-subject",
            "email": "existing-google@test.local",
            "email_verified": True,
            "name": "Existing Admin",
        },
    )
    started = client.get("/auth/google/start?flow=login", follow_redirects=False)
    callback = client.get(
        "/auth/google/callback",
        params={"state": _oauth_state(started.headers["location"]), "code": "verified-code"},
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert callback.headers["location"] == "/ui/mfa/verify"
    assert client.get("/auth/me").status_code == 401

    verified = client.post(
        "/auth/mfa/verify",
        json={"code": current_totp(setup["secret"])},
    )
    assert verified.status_code == 200
    assert client.get("/auth/me").status_code == 200
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="existing-google@test.local").one()
        assert user.google_subject == "existing-google-subject"
