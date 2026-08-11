"""Organization administration, invitation and active-tenant tests."""
from __future__ import annotations

from backend import models
from backend.db import SessionLocal
from backend.tests.helpers import create_exam_manager


def _register(client, email: str, name: str) -> tuple[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "organization_name": name,
            "admin_email": email,
            "admin_password": "matkhau123",
        },
    )
    assert response.status_code == 201
    body = response.json()
    return body["access_token"], body["org_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_org_admin_invites_new_member_and_last_admin_is_protected(client):
    admin_token, _ = _register(client, "org-admin@test.local", "Organization Admin Test")
    invitation = client.post(
        "/organizations/current/invitations",
        json={"email": "teacher@test.local", "role": "exam_manager"},
        headers=_headers(admin_token),
    )
    assert invitation.status_code == 201
    assert invitation.json()["invitation_token"]

    accepted = client.post(
        "/auth/invitations/accept",
        json={
            "invitation_token": invitation.json()["invitation_token"],
            "password": "giaovien123",
        },
    )
    assert accepted.status_code == 201
    teacher_token = accepted.json()["access_token"]

    members = client.get(
        "/organizations/current/members",
        headers=_headers(admin_token),
    )
    assert members.status_code == 200
    by_email = {item["email"]: item for item in members.json()}
    assert by_email["teacher@test.local"]["role"] == "exam_manager"
    assert by_email["teacher@test.local"]["membership_status"] == "active"

    # Exam managers cannot enter organization-administration APIs.
    assert client.get(
        "/organizations/current/members",
        headers=_headers(teacher_token),
    ).status_code == 403

    admin_member = by_email["org-admin@test.local"]
    protected = client.patch(
        f"/organizations/current/members/{admin_member['user_id']}",
        json={"role": "exam_manager"},
        headers=_headers(admin_token),
    )
    assert protected.status_code == 409


def test_organization_audit_is_paged_and_resolves_actor_identity(client):
    admin_token, org_id = _register(
        client,
        "audit-admin@test.local",
        "Audit Organization",
    )
    headers = _headers(admin_token)
    with SessionLocal() as db:
        actor = db.query(models.User).filter_by(email="audit-admin@test.local").one()
        actor.display_name = "Nguyen Audit"
        db.add_all([
            models.AuditLog(
                actor_user_id=actor.id,
                actor_role=actor.role,
                org_id=org_id,
                action="org.audit.pagination",
                resource_type="test_resource",
                resource_id=f"resource-{index:02d}",
                outcome="success",
                reason="Kiem tra phan trang",
            )
            for index in range(25)
        ])
        db.add(
            models.AuditLog(
                actor_user_id=None,
                actor_role=None,
                org_id=org_id,
                action="org.audit.system_event",
                resource_type="test_resource",
                outcome="success",
            )
        )
        db.commit()

    first_page = client.get(
        "/organizations/current/audit/page"
        "?search=org.audit.pagination&page=1&page_size=10",
        headers=headers,
    )
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert first_body["total"] == 25
    assert first_body["page"] == 1
    assert first_body["pages"] == 3
    assert len(first_body["items"]) == 10
    assert first_body["items"][0]["actor_display_name"] == "Nguyen Audit"
    assert first_body["items"][0]["actor_email"] == "audit-admin@test.local"

    sorted_page = client.get(
        "/organizations/current/audit/page"
        "?search=org.audit.pagination&page=1&page_size=10"
        "&sort_by=resource&sort_order=asc",
        headers=headers,
    )
    assert sorted_page.status_code == 200
    assert sorted_page.json()["items"][0]["resource_id"] == "resource-00"

    last_page = client.get(
        "/organizations/current/audit/page"
        "?search=org.audit.pagination&page=3&page_size=10",
        headers=headers,
    )
    assert last_page.status_code == 200
    assert len(last_page.json()["items"]) == 5

    searched_by_user = client.get(
        "/organizations/current/audit/page?search=Nguyen+Audit&page_size=10",
        headers=headers,
    )
    assert searched_by_user.status_code == 200
    assert searched_by_user.json()["total"] >= 25

    system_event = client.get(
        "/organizations/current/audit/page?search=org.audit.system_event&page_size=10",
        headers=headers,
    )
    assert system_event.status_code == 200
    assert system_event.json()["items"][0]["actor_display_name"] is None
    assert system_event.json()["items"][0]["actor_email"] is None

    manager_token = create_exam_manager(
        client,
        admin_token,
        email="audit-manager@test.local",
    )
    assert client.get(
        "/organizations/current/audit/page",
        headers=_headers(manager_token),
    ).status_code == 403


def test_organization_overview_aggregates_exam_and_session_status(client):
    admin_token, _ = _register(
        client,
        "overview-admin@test.local",
        "Overview Organization",
    )
    manager_token = create_exam_manager(
        client,
        admin_token,
        email="overview-manager@test.local",
    )
    exam = client.post(
        "/exams",
        json={"name": "Organization Overview Exam"},
        headers=_headers(manager_token),
    ).json()
    assert client.post(
        "/exams/join",
        json={"join_code": exam["join_code"], "student_name": "Overview Student"},
    ).status_code == 200

    overview = client.get(
        "/organizations/current/overview",
        headers=_headers(admin_token),
    )
    assert overview.status_code == 200
    body = overview.json()
    assert body["members_total"] == 2
    assert body["members_active"] == 2
    assert body["exams_total"] == 1
    assert body["sessions_active"] == 1
    assert body["exam_status"]["open"] == 1
    assert body["session_status"]["pending"] == 1
    assert "quota_usage_percent" in body


def test_org_admin_updates_organization_profile_and_manager_is_forbidden(client):
    admin_token, _ = _register(
        client,
        "settings-admin@test.local",
        "Settings Organization",
    )
    payload = {
        "name": "Updated Settings Organization",
        "logo_url": "https://assets.example.test/logo.png",
        "address": "123 Duong Nguyen Van Linh, Da Nang",
        "email": "contact@example.test",
        "phone": "+84 236 123 4567",
        "website": "https://example.test",
    }
    updated = client.patch(
        "/organizations/current",
        json=payload,
        headers=_headers(admin_token),
    )
    assert updated.status_code == 200
    assert {key: updated.json()[key] for key in payload} == payload

    loaded = client.get(
        "/organizations/current",
        headers=_headers(admin_token),
    )
    assert loaded.status_code == 200
    assert loaded.json()["address"] == payload["address"]

    insecure_logo = client.patch(
        "/organizations/current",
        json={**payload, "logo_url": "http://assets.example.test/logo.png"},
        headers=_headers(admin_token),
    )
    assert insecure_logo.status_code == 422

    http_website = client.patch(
        "/organizations/current",
        json={**payload, "website": "http://example.test"},
        headers=_headers(admin_token),
    )
    assert http_website.status_code == 200
    assert http_website.json()["website"] == "http://example.test"

    manager_token = create_exam_manager(
        client,
        admin_token,
        email="settings-manager@test.local",
    )
    forbidden = client.patch(
        "/organizations/current",
        json={**payload, "name": "Unauthorized Update"},
        headers=_headers(manager_token),
    )
    assert forbidden.status_code == 403


def test_existing_user_can_join_and_switch_between_organizations(client):
    first_admin_token, first_org_id = _register(
        client,
        "first-admin@test.local",
        "First Organization",
    )
    second_admin_token, second_org_id = _register(
        client,
        "shared-user@test.local",
        "Second Organization",
    )

    invitation = client.post(
        "/organizations/current/invitations",
        json={"email": "shared-user@test.local", "role": "exam_manager"},
        headers=_headers(first_admin_token),
    )
    assert invitation.status_code == 201
    accepted = client.post(
        "/auth/invitations/accept",
        json={
            "invitation_token": invitation.json()["invitation_token"],
            "password": "matkhau123",
        },
    )
    assert accepted.status_code == 201
    assert accepted.json()["org_id"] == first_org_id
    first_org_teacher_token = accepted.json()["access_token"]

    organizations = client.get(
        "/auth/organizations",
        headers=_headers(first_org_teacher_token),
    )
    assert organizations.status_code == 200
    assert {item["id"] for item in organizations.json()} == {first_org_id, second_org_id}

    # The active tenant is encoded in a newly issued server token. Creating an
    # exam while switched must use that tenant, not legacy User.org_id.
    created_in_first = client.post(
        "/exams",
        json={"name": "Exam in First Org"},
        headers=_headers(first_org_teacher_token),
    )
    assert created_in_first.status_code == 201

    switched = client.post(
        f"/auth/switch-organization/{second_org_id}",
        headers=_headers(first_org_teacher_token),
    )
    assert switched.status_code == 200
    assert switched.json()["role"] == "admin"
    second_org_token = switched.json()["access_token"]
    assert client.get("/exams", headers=_headers(second_org_token)).json() == []

    # Keep the variable used so the test also proves the original admin token
    # remains a valid credential for its own organization.
    assert client.get("/exams", headers=_headers(second_admin_token)).status_code == 200


def test_org_policy_is_validated_and_persisted(client):
    admin_token, _ = _register(client, "policy-admin@test.local", "Policy Org")
    payload = {
        "default_candidate_auth_mode": "manual",
        "min_extension_version": "2.1.0",
        "require_extension": True,
        "require_fullscreen": True,
        "require_camera": True,
        "require_microphone": True,
        "require_screen_share": False,
        "block_clipboard": True,
        "max_focus_loss_seconds": 3.5,
        "retention_days": 180,
    }
    updated = client.put(
        "/organizations/current/policy",
        json=payload,
        headers=_headers(admin_token),
    )
    assert updated.status_code == 200
    loaded = client.get(
        "/organizations/current/policy",
        headers=_headers(admin_token),
    )
    assert loaded.status_code == 200
    assert loaded.json() == payload

    invalid = client.put(
        "/organizations/current/policy",
        json={**payload, "retention_days": 0},
        headers=_headers(admin_token),
    )
    assert invalid.status_code == 422


def test_exam_inherits_org_policy_and_cannot_weaken_it(client):
    admin_token, _ = _register(client, "policy-floor-admin@test.local", "Policy Floor Org")
    policy = {
        "default_candidate_auth_mode": "manual",
        "min_extension_version": "2.1.0",
        "require_extension": True,
        "require_fullscreen": True,
        "require_camera": True,
        "require_microphone": True,
        "require_screen_share": False,
        "block_clipboard": True,
        "max_focus_loss_seconds": 3.5,
        "retention_days": 180,
    }
    assert client.put(
        "/organizations/current/policy",
        json=policy,
        headers=_headers(admin_token),
    ).status_code == 200
    manager_token = create_exam_manager(
        client,
        admin_token,
        email="policy-floor-manager@test.local",
    )
    headers = _headers(manager_token)

    defaults = client.get("/exams/policy/defaults", headers=headers)
    assert defaults.status_code == 200
    assert defaults.json() == policy

    inherited = client.post(
        "/exams",
        json={"name": "Inherited Policy", "exam_url": "https://exam.test/"},
        headers=headers,
    )
    assert inherited.status_code == 201
    assert inherited.json()["min_extension_version"] == "2.1.0"
    assert inherited.json()["require_microphone"] is True
    assert inherited.json()["max_focus_loss_seconds"] == 3.5

    weakened = client.post(
        "/exams",
        json={
            "name": "Weak Policy",
            "exam_url": "https://exam.test/",
            "require_microphone": False,
        },
        headers=headers,
    )
    assert weakened.status_code == 422
    assert "require_microphone" in weakened.json()["detail"]


def test_platform_policy_floor_rejects_weaker_organization_policy(client):
    admin_token, _ = _register(client, "platform-floor-admin@test.local", "Platform Floor Org")
    with SessionLocal() as db:
        db.add(
            models.PlatformPolicySetting(
                id="default",
                settings_json=(
                    '{"min_extension_version":"3.0.0",'
                    '"require_screen_share":true,"max_focus_loss_seconds":10}'
                ),
            )
        )
        db.commit()

    current = client.get(
        "/organizations/current/policy",
        headers=_headers(admin_token),
    )
    assert current.status_code == 200
    assert current.json()["min_extension_version"] == "3.0.0"
    assert current.json()["require_screen_share"] is True

    weaker = {**current.json(), "require_screen_share": False}
    rejected = client.put(
        "/organizations/current/policy",
        json=weaker,
        headers=_headers(admin_token),
    )
    assert rejected.status_code == 422


def test_concurrent_session_quota_is_enforced(client):
    admin_token, org_id = _register(client, "quota-admin@test.local", "Quota Org")
    with SessionLocal() as db:
        organization = db.get(models.Organization, org_id)
        organization.quota_concurrent_sessions = 1
        db.commit()
    manager_token = create_exam_manager(
        client,
        admin_token,
        email="quota-manager@test.local",
    )
    exam = client.post(
        "/exams",
        json={"name": "Quota Exam"},
        headers=_headers(manager_token),
    ).json()
    first = client.post(
        "/exams/join",
        json={"join_code": exam["join_code"], "student_name": "First"},
    )
    assert first.status_code == 200
    second = client.post(
        "/exams/join",
        json={"join_code": exam["join_code"], "student_name": "Second"},
    )
    assert second.status_code == 429
