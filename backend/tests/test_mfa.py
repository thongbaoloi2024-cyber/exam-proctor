"""MFA enrollment and System Admin enforcement tests."""
from __future__ import annotations

import base64

from backend import models
from backend.db import SessionLocal
from backend.mfa import current_totp


def test_system_admin_must_enroll_mfa_and_login_with_second_factor(client):
    registered = client.post(
        "/auth/register",
        json={
            "organization_name": "MFA System Org",
            "admin_email": "mfa-system@test.local",
            "admin_password": "matkhau123",
        },
    )
    initial_token = registered.json()["access_token"]
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="mfa-system@test.local").one()
        db.add(
            models.SystemRole(
                user_id=user.id,
                role="system_admin",
                status="pending_mfa",
            )
        )
        db.commit()

    assert client.get(
        "/system/overview",
        headers={"Authorization": f"Bearer {initial_token}"},
    ).status_code == 403
    login = client.post(
        "/auth/login",
        json={"email": "mfa-system@test.local", "password": "matkhau123"},
    )
    assert login.status_code == 200
    assert login.json()["mfa_setup_required"] is True
    setup_token = login.json()["access_token"]

    setup = client.post(
        "/auth/mfa/setup",
        headers={"Authorization": f"Bearer {setup_token}"},
    )
    assert setup.status_code == 200
    assert len(setup.json()["recovery_codes"]) == 8
    qr_data_url = setup.json()["qr_code_data_url"]
    assert qr_data_url.startswith("data:image/png;base64,")
    assert base64.b64decode(qr_data_url.split(",", 1)[1]).startswith(b"\x89PNG\r\n\x1a\n")
    code = current_totp(setup.json()["secret"])
    confirmed = client.post(
        "/auth/mfa/confirm",
        json={"code": code},
        headers={"Authorization": f"Bearer {setup_token}"},
    )
    assert confirmed.status_code == 200
    active_token = confirmed.json()["access_token"]
    assert client.get(
        "/system/overview",
        headers={"Authorization": f"Bearer {active_token}"},
    ).status_code == 200
    assert client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {setup_token}"},
    ).status_code == 401

    primary_login = client.post(
        "/auth/login",
        json={"email": "mfa-system@test.local", "password": "matkhau123"},
    )
    assert primary_login.status_code == 200
    assert primary_login.json()["mfa_required"] is True
    assert primary_login.json()["access_token"] is None
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/mfa/challenge").json()["attempts_remaining"] == 3
    recovery_login = client.post(
        "/auth/mfa/verify",
        json={"code": setup.json()["recovery_codes"][0]},
    )
    assert recovery_login.status_code == 200
    assert recovery_login.json()["role"] == "system_admin"
    client.post(
        "/auth/login",
        json={"email": "mfa-system@test.local", "password": "matkhau123"},
    )
    reused = client.post(
        "/auth/mfa/verify",
        json={"code": setup.json()["recovery_codes"][0]},
    )
    assert reused.status_code == 401


def test_mfa_confirmation_does_not_reactivate_revoked_system_role(client):
    registered = client.post(
        "/auth/register",
        json={
            "organization_name": "Revoked MFA Org",
            "admin_email": "revoked-mfa@test.local",
            "admin_password": "matkhau123",
        },
    )
    token = registered.json()["access_token"]
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="revoked-mfa@test.local").one()
        db.add(models.SystemRole(user_id=user.id, role="system_admin", status="revoked"))
        db.commit()

    setup = client.post(
        "/auth/mfa/setup",
        headers={"Authorization": f"Bearer {token}"},
    )
    code = current_totp(setup.json()["secret"])
    confirmed = client.post(
        "/auth/mfa/confirm",
        json={"code": code},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert confirmed.status_code == 200
    with SessionLocal() as db:
        role = db.query(models.SystemRole).filter_by(role="system_admin").one()
        assert role.status == "revoked"
    assert client.get(
        "/system/overview",
        headers={"Authorization": f"Bearer {confirmed.json()['access_token']}"},
    ).status_code == 403


def test_broken_mfa_encryption_uses_recovery_code_and_forces_reenrollment(client):
    registered = client.post(
        "/auth/register",
        json={
            "organization_name": "Broken MFA Recovery Org",
            "admin_email": "broken-mfa@test.local",
            "admin_password": "matkhau123",
        },
    )
    initial_token = registered.json()["access_token"]
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="broken-mfa@test.local").one()
        db.add(models.SystemRole(user_id=user.id, role="system_admin", status="pending_mfa"))
        db.commit()
    setup = client.post(
        "/auth/mfa/setup",
        headers={"Authorization": f"Bearer {initial_token}"},
    ).json()
    confirmed = client.post(
        "/auth/mfa/confirm",
        json={"code": current_totp(setup["secret"])},
        headers={"Authorization": f"Bearer {initial_token}"},
    )
    assert confirmed.status_code == 200
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="broken-mfa@test.local").one()
        user.mfa_secret_encrypted = "not-a-valid-fernet-token"
        db.commit()

    primary_login = client.post(
        "/auth/login",
        json={"email": "broken-mfa@test.local", "password": "matkhau123"},
    )
    assert primary_login.json()["mfa_required"] is True
    controlled_error = client.post("/auth/mfa/verify", json={"code": "invalid-code"})
    assert controlled_error.status_code == 409
    assert controlled_error.json()["attempts_remaining"] == 2

    recovered = client.post(
        "/auth/mfa/verify",
        json={"code": setup["recovery_codes"][0]},
    )
    assert recovered.status_code == 200
    assert recovered.json()["mfa_setup_required"] is True
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="broken-mfa@test.local").one()
        role = db.query(models.SystemRole).filter_by(user_id=user.id, role="system_admin").one()
        assert user.mfa_enabled is False
        assert user.mfa_secret_encrypted is None
        assert user.mfa_recovery_codes_json is None
        assert role.status == "pending_mfa"


def test_mfa_challenge_allows_only_three_failed_attempts(client):
    registered = client.post(
        "/auth/register",
        json={
            "organization_name": "MFA Attempt Org",
            "admin_email": "mfa-attempt@test.local",
            "admin_password": "matkhau123",
        },
    )
    token = registered.json()["access_token"]
    setup = client.post(
        "/auth/mfa/setup",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    client.post(
        "/auth/mfa/confirm",
        json={"code": current_totp(setup["secret"])},
        headers={"Authorization": f"Bearer {token}"},
    )
    login = client.post(
        "/auth/login",
        json={"email": "mfa-attempt@test.local", "password": "matkhau123"},
    )
    assert login.json()["mfa_required"] is True

    for remaining in (2, 1, 0):
        invalid = client.post("/auth/mfa/verify", json={"code": "invalid-code"})
        assert invalid.status_code == 401
        assert invalid.json()["attempts_remaining"] == remaining

    assert client.get("/auth/mfa/challenge").status_code == 401
    blocked_valid_code = client.post(
        "/auth/mfa/verify",
        json={"code": current_totp(setup["secret"])},
    )
    assert blocked_valid_code.status_code == 401
