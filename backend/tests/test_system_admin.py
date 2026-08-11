"""System Admin isolation, tenant operations and break-glass tests."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from backend import models
from backend.db import SessionLocal
from backend.tests.helpers import create_exam_manager
from scripts import bootstrap_system_admin


def _register(client, email: str, organization: str) -> tuple[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "organization_name": organization,
            "admin_email": email,
            "admin_password": "matkhau123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"], response.json()["org_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _grant_system_role(email: str) -> None:
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email=email).one()
        user.mfa_enabled = True
        db.add(
            models.SystemRole(
                user_id=user.id,
                role="system_admin",
                status="active",
            )
        )
        db.commit()


def test_system_admin_needs_approved_break_glass_for_evidence(client):
    system_token, _ = _register(client, "system-admin@test.local", "System Home")
    _grant_system_role("system-admin@test.local")
    target_token, target_org_id = _register(client, "target-admin@test.local", "Target Org")
    target_headers = _headers(target_token)
    target_manager_token = create_exam_manager(
        client,
        target_token,
        email="target-manager@test.local",
    )
    exam = client.post(
        "/exams",
        json={"name": "Sensitive Exam"},
        headers=_headers(target_manager_token),
    ).json()
    joined = client.post(
        "/exams/join",
        json={"join_code": exam["join_code"], "student_name": "Sensitive Student"},
    ).json()
    system_headers = _headers(system_token)

    capabilities_before = client.get("/auth/me", headers=system_headers).json()["capabilities"]
    assert "system.organizations.manage" in capabilities_before
    assert "org.members.manage" not in capabilities_before
    assert "exam.read" not in capabilities_before

    assert client.get("/system/overview", headers=system_headers).status_code == 200
    assert client.get("/system/overview", headers=target_headers).status_code == 403
    assert client.get(f"/exams/{exam['id']}", headers=system_headers).status_code == 403
    assert client.get(
        f"/sessions/{joined['session_id']}/detail",
        headers=system_headers,
    ).status_code == 403

    requested = client.post(
        "/system/access-grants",
        json={
            "org_id": target_org_id,
            "reason": "Ho tro dieu tra su co theo yeu cau cua to chuc",
            "scope": "evidence.read",
            "requested_duration_minutes": 30,
        },
        headers=system_headers,
    )
    assert requested.status_code == 201
    assert requested.json()["status"] == "pending"

    visible_request = client.get(
        "/organizations/current/access-grants",
        headers=target_headers,
    )
    assert visible_request.status_code == 200
    assert visible_request.json()[0]["requester_email"] == "system-admin@test.local"
    assert visible_request.json()[0]["scope"] == "evidence.read"
    assert visible_request.json()[0]["read_only"] is True

    denied_reauth = client.post(
        f"/organizations/current/access-grants/{requested.json()['id']}/approve",
        json={"decision_reason": "Khong dung ma", "verification_code": "sai-mat-khau"},
        headers=target_headers,
    )
    assert denied_reauth.status_code == 401

    approved = client.post(
        f"/organizations/current/access-grants/{requested.json()['id']}/approve",
        json={
            "decision_reason": "Da xac minh yeu cau ho tro",
            "verification_code": "matkhau123",
        },
        headers=target_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "active"

    capabilities_after = client.get("/auth/me", headers=system_headers).json()["capabilities"]
    assert "exam.read" in capabilities_after
    assert "exam.monitor" in capabilities_after
    assert "exam.evidence.read" in capabilities_after
    assert "exam.manage" not in capabilities_after
    assert "exam.sessions.end" not in capabilities_after
    granted_exams = client.get("/exams", headers=system_headers)
    assert granted_exams.status_code == 200
    assert [item["id"] for item in granted_exams.json()] == [exam["id"]]
    assert granted_exams.json()[0]["join_code"] is None
    assert granted_exams.json()[0]["exam_url"] is None
    assert client.get(
        f"/exams/{exam['id']}/sessions",
        headers=system_headers,
    ).status_code == 200

    detail = client.get(
        f"/sessions/{joined['session_id']}/detail",
        headers=system_headers,
    )
    assert detail.status_code == 200
    # Break-glass is read-only and never permits operational intervention.
    assert client.post(
        f"/sessions/{joined['session_id']}/end",
        headers=system_headers,
    ).status_code == 403

    revoked = client.post(
        f"/organizations/current/access-grants/{requested.json()['id']}/revoke",
        json={
            "decision_reason": "Da hoan tat dieu tra",
            "verification_code": "matkhau123",
        },
        headers=target_headers,
    )
    assert revoked.status_code == 200
    assert client.get("/exams", headers=system_headers).json() == []
    assert client.get(
        f"/exams/{exam['id']}/sessions",
        headers=system_headers,
    ).status_code == 403
    assert client.get(
        f"/sessions/{joined['session_id']}/detail",
        headers=system_headers,
    ).status_code == 403

    audit = client.get("/system/audit", headers=system_headers)
    assert audit.status_code == 200
    actions = {item["action"] for item in audit.json()}
    assert "system.break_glass.request" in actions
    assert "org.break_glass.approve" in actions
    assert "org.break_glass.revoke" in actions
    evidence_entries = [
        item for item in audit.json() if item["action"] == "exam.evidence.view"
    ]
    assert evidence_entries
    assert evidence_entries[0]["access_grant_id"] == requested.json()["id"]


def test_system_admin_can_provision_and_suspend_organization(client):
    system_token, _ = _register(client, "provision-system@test.local", "System Tenant")
    _grant_system_role("provision-system@test.local")
    headers = _headers(system_token)
    created = client.post(
        "/system/organizations",
        json={
            "name": "Provisioned Organization",
            "admin_email": "provisioned-admin@test.local",
            "retention_days": 180,
            "quota_concurrent_sessions": 50,
        },
        headers=headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["organization"]["status"] == "active"
    invited_admin = client.post(
        f"/system/organizations/{body['organization']['id']}/admin-invitations",
        json={"email": "second-provisioned-admin@test.local", "expires_in_hours": 48},
        headers=headers,
    )
    assert invited_admin.status_code == 201
    assert invited_admin.json()["invitation_token"]
    accepted = client.post(
        "/auth/invitations/accept",
        json={
            "invitation_token": body["admin_invitation_token"],
            "password": "provisioned123",
        },
    )
    assert accepted.status_code == 201
    provisioned_token = accepted.json()["access_token"]

    suspended = client.patch(
        f"/system/organizations/{body['organization']['id']}",
        json={"status": "suspended", "reason": "Tam khoa theo yeu cau van hanh"},
        headers=headers,
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    assert client.get(
        "/auth/me",
        headers=_headers(provisioned_token),
    ).status_code == 401


def test_system_admin_analytics_and_paged_directories(client):
    system_token, _ = _register(client, "analytics-system@test.local", "System Analytics")
    _grant_system_role("analytics-system@test.local")
    target_token, target_org_id = _register(client, "analytics-target@test.local", "Analytics Target")
    target_headers = _headers(target_token)
    target_manager_token = create_exam_manager(
        client,
        target_token,
        email="analytics-manager@test.local",
    )
    exam = client.post(
        "/exams",
        json={"name": "Analytics Exam"},
        headers=_headers(target_manager_token),
    ).json()
    client.post(
        "/exams/join",
        json={"join_code": exam["join_code"], "student_name": "Analytics Student"},
    )
    system_headers = _headers(system_token)

    analytics = client.get("/system/analytics/overview?days=30", headers=system_headers)
    assert analytics.status_code == 200
    analytics_body = analytics.json()
    assert analytics_body["totals"]["organizations"] == 2
    assert analytics_body["totals"]["users"] == 3
    assert len(analytics_body["session_trend"]) == 30
    assert any(item["key"] == "active" for item in analytics_body["organization_status"])

    directory = client.get(
        "/system/organizations/page?search=Analytics+Target&page=1&page_size=5",
        headers=system_headers,
    )
    assert directory.status_code == 200
    assert directory.json()["total"] == 1
    assert directory.json()["items"][0]["exam_count"] == 1
    assert directory.json()["items"][0]["active_session_count"] == 1

    detail = client.get(f"/system/organizations/{target_org_id}", headers=system_headers)
    assert detail.status_code == 200
    assert detail.json()["organization"]["name"] == "Analytics Target"
    assert detail.json()["administrators"][0]["email"] == "analytics-target@test.local"

    requested = client.post(
        "/system/access-grants",
        json={
            "org_id": target_org_id,
            "reason": "Dieu tra su co cho bai test analytics",
            "scope": "evidence.read",
            "requested_duration_minutes": 30,
        },
        headers=system_headers,
    )
    assert requested.status_code == 201
    grants = client.get("/system/access-grants?status=pending", headers=system_headers)
    assert grants.status_code == 200
    assert grants.json()["items"][0]["organization_name"] == "Analytics Target"

    audit_page = client.get(
        "/system/audit/page?search=system.break_glass&page_size=10",
        headers=system_headers,
    )
    assert audit_page.status_code == 200
    assert audit_page.json()["total"] == 1
    assert audit_page.json()["items"][0]["reason"]


def test_internal_system_tenant_cannot_be_updated_or_suspended(client):
    system_token, org_id = _register(client, "protected-system@test.local", "Protected System")
    _grant_system_role("protected-system@test.local")
    with SessionLocal() as db:
        organization = db.get(models.Organization, org_id)
        organization.slug = "system"
        db.commit()

    headers = _headers(system_token)
    response = client.patch(
        f"/system/organizations/{org_id}",
        json={"status": "suspended", "reason": "Should never be allowed"},
        headers=headers,
    )
    assert response.status_code == 409
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.get("/system/organizations", headers=headers).json() == []


def test_bootstrap_existing_mfa_user_activates_role_in_system_tenant(client, monkeypatch):
    _token, original_org_id = _register(
        client,
        "existing-mfa-bootstrap@test.local",
        "Existing MFA Bootstrap",
    )
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="existing-mfa-bootstrap@test.local").one()
        user.mfa_enabled = True
        db.commit()

    monkeypatch.setattr(
        sys,
        "argv",
        ["bootstrap_system_admin.py", "--email", "existing-mfa-bootstrap@test.local"],
    )
    bootstrap_system_admin.main()

    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="existing-mfa-bootstrap@test.local").one()
        role = db.query(models.SystemRole).filter_by(user_id=user.id, role="system_admin").one()
        system_org = db.query(models.Organization).filter_by(slug="system").one()
        membership = db.query(models.OrganizationMembership).filter_by(
            user_id=user.id,
            org_id=system_org.id,
        ).one()
        assert role.status == "active"
        assert user.org_id == system_org.id
        assert user.org_id != original_org_id
        assert membership.status == "active"


def test_expired_pending_grant_is_not_counted_as_pending(client):
    system_token, _ = _register(client, "expired-grant-system@test.local", "Expired System")
    _grant_system_role("expired-grant-system@test.local")
    _target_token, target_org_id = _register(client, "expired-grant-target@test.local", "Expired Target")
    with SessionLocal() as db:
        requester = db.query(models.User).filter_by(email="expired-grant-system@test.local").one()
        db.add(models.AccessGrant(
            requester_user_id=requester.id,
            org_id=target_org_id,
            reason="Expired pending grant regression probe",
            scope="evidence.read",
            status="pending",
            read_only=True,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        ))
        db.commit()
    overview = client.get("/system/overview", headers=_headers(system_token))
    assert overview.status_code == 200
    assert overview.json()["pending_access_grants"] == 0


def test_system_operations_and_policy_are_managed_with_optimistic_lock(client):
    system_token, _ = _register(client, "policy-system@test.local", "Policy System")
    _grant_system_role("policy-system@test.local")
    headers = _headers(system_token)

    operations = client.get("/system/operations", headers=headers)
    assert operations.status_code == 200
    assert operations.json()["database_status"] == "healthy"
    assert "report_jobs" in operations.json()

    current = client.get("/system/policy", headers=headers)
    assert current.status_code == 200
    assert current.json()["version"] == 0
    policy = current.json()["policy"]
    policy.update({
        "min_extension_version": "2.1.0",
        "require_extension": True,
        "min_retention_days": 30,
        "max_retention_days": 730,
    })
    updated = client.put(
        "/system/policy",
        json={"policy": policy, "expected_version": 0, "reason": "Nang security floor"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 1
    assert updated.json()["policy"]["min_extension_version"] == "2.1.0"

    stale = client.put(
        "/system/policy",
        json={"policy": policy, "expected_version": 0, "reason": "Stale update"},
        headers=headers,
    )
    assert stale.status_code == 409
