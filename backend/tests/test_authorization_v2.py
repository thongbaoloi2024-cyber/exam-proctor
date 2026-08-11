"""Capability, tenant and exam-assignment regression tests."""
from __future__ import annotations

from backend import models
from backend.db import SessionLocal


def _register_admin(client, email: str = "authz-admin@test.local") -> str:
    response = client.post(
        "/auth/register",
        json={
            "organization_name": "Authorization Org",
            "admin_email": email,
            "admin_password": "matkhau123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _create_proctor(client, admin_token: str, email: str) -> tuple[str, str]:
    response = client.post(
        "/auth/proctors",
        json={"email": email, "password": "matkhau123"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "matkhau123"},
    )
    assert login.status_code == 200
    return response.json()["id"], login.json()["access_token"]


def _create_exam(client, token: str, name: str = "Scoped Exam") -> dict:
    response = client.post(
        "/exams",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


def test_exam_manager_only_lists_assigned_exams(client):
    admin_token = _register_admin(client)
    _, creator_token = _create_proctor(client, admin_token, "creator-owner@test.local")
    exam = _create_exam(client, creator_token)
    proctor_id, proctor_token = _create_proctor(
        client,
        admin_token,
        "unassigned@test.local",
    )
    proctor_headers = {"Authorization": f"Bearer {proctor_token}"}

    assert client.get("/exams", headers=proctor_headers).json() == []
    hidden = client.get(f"/exams/{exam['id']}/sessions", headers=proctor_headers)
    assert hidden.status_code == 404

    with SessionLocal() as db:
        db.add(
            models.ExamAssignment(
                exam_id=exam["id"],
                user_id=proctor_id,
                assignment_role="proctor",
                status="active",
            )
        )
        db.commit()

    listed = client.get("/exams", headers=proctor_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [exam["id"]]
    assert client.get(f"/exams/{exam['id']}/sessions", headers=proctor_headers).status_code == 200

    # A proctor can monitor but cannot change exam lifecycle/configuration.
    forbidden = client.patch(
        f"/exams/{exam['id']}/status",
        json={"status": "closed"},
        headers=proctor_headers,
    )
    assert forbidden.status_code == 403


def test_manager_assignment_can_manage_exam(client):
    admin_token = _register_admin(client, email="manager-admin@test.local")
    _, creator_token = _create_proctor(client, admin_token, "manager-owner@test.local")
    exam = _create_exam(client, creator_token, "Manager Exam")
    manager_id, manager_token = _create_proctor(
        client,
        admin_token,
        "manager@test.local",
    )
    with SessionLocal() as db:
        db.add(
            models.ExamAssignment(
                exam_id=exam["id"],
                user_id=manager_id,
                assignment_role="manager",
                status="active",
            )
        )
        db.commit()

    response = client.patch(
        f"/exams/{exam['id']}/status",
        json={"status": "closed"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_exam_response_actions_are_scoped_per_assignment(client):
    admin_token = _register_admin(client, email="mixed-scope-admin@test.local")
    _, owner_token = _create_proctor(client, admin_token, "mixed-owner@test.local")
    manager_exam = _create_exam(client, owner_token, "Managed Resource")
    proctor_exam = _create_exam(client, owner_token, "Proctored Resource")
    mixed_user_id, mixed_token = _create_proctor(
        client,
        admin_token,
        "mixed-role@test.local",
    )
    with SessionLocal() as db:
        db.add_all([
            models.ExamAssignment(
                exam_id=manager_exam["id"],
                user_id=mixed_user_id,
                assignment_role="manager",
                status="active",
            ),
            models.ExamAssignment(
                exam_id=proctor_exam["id"],
                user_id=mixed_user_id,
                assignment_role="proctor",
                status="active",
            ),
        ])
        db.commit()

    response = client.get(
        "/exams",
        headers={"Authorization": f"Bearer {mixed_token}"},
    )
    assert response.status_code == 200
    exams = {item["id"]: item for item in response.json()}

    managed = exams[manager_exam["id"]]
    assert managed["assignment_role"] == "manager"
    assert "exam.manage" in managed["allowed_actions"]
    assert "closed" in managed["allowed_transitions"]

    proctored = exams[proctor_exam["id"]]
    assert proctored["assignment_role"] == "proctor"
    assert "exam.monitor" in proctored["allowed_actions"]
    assert "exam.manage" not in proctored["allowed_actions"]
    assert proctored["allowed_transitions"] == []


def test_exam_manager_can_create_and_owns_new_exam(client):
    admin_token = _register_admin(client, email="creator-admin@test.local")
    proctor_id, proctor_token = _create_proctor(
        client,
        admin_token,
        "creator@test.local",
    )
    exam = _create_exam(client, proctor_token, "Teacher-owned Exam")

    with SessionLocal() as db:
        stored = db.get(models.Exam, exam["id"])
        assert stored is not None
        assert stored.owner_user_id == proctor_id
        assignment = db.query(models.ExamAssignment).filter_by(
            exam_id=exam["id"],
            user_id=proctor_id,
        ).one()
        assert assignment.assignment_role == "owner"


def test_org_admin_has_no_exam_access_even_with_stale_owner_assignment(client):
    admin_token = _register_admin(client, email="strict-org-admin@test.local")
    _, creator_token = _create_proctor(
        client,
        admin_token,
        "strict-exam-owner@test.local",
    )
    exam = _create_exam(client, creator_token, "Strict Role Boundary Exam")

    with SessionLocal() as db:
        admin = db.query(models.User).filter_by(email="strict-org-admin@test.local").one()
        db.add(
            models.ExamAssignment(
                exam_id=exam["id"],
                user_id=admin.id,
                assignment_role="owner",
                status="active",
            )
        )
        db.commit()

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    capabilities = client.get("/auth/me", headers=admin_headers).json()["capabilities"]
    assert not any(capability.startswith("exam.") for capability in capabilities)
    assert client.get("/exams", headers=admin_headers).json() == []
    assert client.get(f"/exams/{exam['id']}", headers=admin_headers).status_code == 403
    assert client.post(
        "/exams",
        json={"name": "Forbidden Org Admin Exam"},
        headers=admin_headers,
    ).status_code == 403


def test_membership_and_session_version_revocation_take_effect(client):
    admin_token = _register_admin(client, email="revoke-admin@test.local")
    proctor_id, proctor_token = _create_proctor(
        client,
        admin_token,
        "revoke@test.local",
    )
    headers = {"Authorization": f"Bearer {proctor_token}"}
    assert client.get("/exams", headers=headers).status_code == 200

    with SessionLocal() as db:
        membership = db.query(models.OrganizationMembership).filter_by(
            user_id=proctor_id,
        ).one()
        membership.status = "revoked"
        db.commit()
    assert client.get("/exams", headers=headers).status_code == 401

    with SessionLocal() as db:
        user = db.get(models.User, proctor_id)
        assert user is not None
        membership = db.query(models.OrganizationMembership).filter_by(
            user_id=proctor_id,
        ).one()
        membership.status = "active"
        user.session_version += 1
        db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_unassigned_exam_manager_cannot_open_dashboard_websocket(client):
    admin_token = _register_admin(client, email="ws-scope-admin@test.local")
    _, creator_token = _create_proctor(client, admin_token, "ws-owner@test.local")
    exam = _create_exam(client, creator_token, "WS Scoped Exam")
    _, proctor_token = _create_proctor(
        client,
        admin_token,
        "ws-unassigned@test.local",
    )

    connected = False
    try:
        with client.websocket_connect(
            f"/ws/dashboard/{exam['id']}",
            headers={"Authorization": f"Bearer {proctor_token}"},
        ):
            connected = True
    except Exception:
        pass
    assert connected is False
