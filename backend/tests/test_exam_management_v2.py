"""Exam lifecycle, assignment and incident-review tests."""
from __future__ import annotations

from pathlib import Path

import backend.session_materializer as session_materializer
from backend.db import SessionLocal
from backend import models


def _register_admin(client, email: str = "exam-v2-admin@test.local") -> str:
    response = client.post(
        "/auth/register",
        json={
            "organization_name": "Exam Management Org",
            "admin_email": email,
            "admin_password": "matkhau123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_teacher(client, admin_token: str, email: str) -> tuple[str, str]:
    created = client.post(
        "/auth/proctors",
        json={"email": email, "password": "matkhau123"},
        headers=_headers(admin_token),
    )
    assert created.status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "matkhau123"},
    )
    assert login.status_code == 200
    return created.json()["id"], login.json()["access_token"]


def _register_exam_owner(client, admin_email: str) -> tuple[str, str]:
    admin_token = _register_admin(client, admin_email)
    _, owner_token = _create_teacher(
        client,
        admin_token,
        admin_email.replace("@", "-owner@"),
    )
    return admin_token, owner_token


def test_exam_lifecycle_and_optimistic_locking(client):
    _, token = _register_exam_owner(client, "exam-v2-admin@test.local")
    headers = _headers(token)
    created = client.post(
        "/exams",
        json={"name": "Draft Exam", "initial_status": "draft"},
        headers=headers,
    )
    assert created.status_code == 201
    exam = created.json()
    assert exam["status"] == "draft"
    assert exam["version"] == 1

    updated = client.patch(
        f"/exams/{exam['id']}",
        json={
            "expected_version": 1,
            "name": "Scheduled Exam",
            "scheduled_start_at": "2026-08-10T08:00:00+07:00",
            "scheduled_end_at": "2026-08-10T10:00:00+07:00",
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    stale = client.patch(
        f"/exams/{exam['id']}",
        json={"expected_version": 1, "name": "Stale write"},
        headers=headers,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["current_version"] == 2

    scheduled = client.patch(
        f"/exams/{exam['id']}/status",
        json={"status": "scheduled", "expected_version": 2},
        headers=headers,
    )
    assert scheduled.status_code == 200
    assert scheduled.json()["version"] == 3

    opened = client.patch(
        f"/exams/{exam['id']}/status",
        json={"status": "open", "expected_version": 3},
        headers=headers,
    )
    assert opened.status_code == 200
    invalid_transition = client.patch(
        f"/exams/{exam['id']}/status",
        json={"status": "draft", "expected_version": 4},
        headers=headers,
    )
    assert invalid_transition.status_code == 409

    closed = client.patch(
        f"/exams/{exam['id']}/status",
        json={"status": "closed", "expected_version": 4},
        headers=headers,
    )
    assert closed.status_code == 200
    archived = client.patch(
        f"/exams/{exam['id']}/status",
        json={"status": "archived", "expected_version": 5},
        headers=headers,
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"]


def test_assignment_api_controls_exam_scope(client):
    admin_token, owner_token = _register_exam_owner(client, "assign-admin@test.local")
    headers = _headers(owner_token)
    exam = client.post("/exams", json={"name": "Assigned Exam"}, headers=headers).json()
    teacher_id, teacher_token = _create_teacher(
        client,
        admin_token,
        "assigned-teacher@test.local",
    )

    assigned = client.put(
        f"/exams/{exam['id']}/assignments",
        json={"user_id": teacher_id, "assignment_role": "manager"},
        headers=headers,
    )
    assert assigned.status_code == 200
    assert assigned.json()["assignment_role"] == "manager"
    assert [item["id"] for item in client.get(
        "/exams",
        headers=_headers(teacher_token),
    ).json()] == [exam["id"]]

    owner_revoke = client.delete(
        f"/exams/{exam['id']}/assignments/{exam['owner_user_id']}",
        headers=headers,
    )
    assert owner_revoke.status_code == 409

    revoked = client.delete(
        f"/exams/{exam['id']}/assignments/{teacher_id}",
        headers=headers,
    )
    assert revoked.status_code == 204
    assert client.get("/exams", headers=_headers(teacher_token)).json() == []


def test_incident_review_is_separate_from_violation_log(client, tmp_path, monkeypatch):
    monkeypatch.setattr(session_materializer, "SESSIONS_ROOT", tmp_path)
    _, token = _register_exam_owner(client, "review-admin@test.local")
    headers = _headers(token)
    exam = client.post("/exams", json={"name": "Review Exam"}, headers=headers).json()
    joined = client.post(
        "/exams/join",
        json={"join_code": exam["join_code"], "student_name": "Review Student"},
    ).json()
    session_materializer.append_jsonl(
        joined["session_id"],
        "violations.jsonl",
        {
            "event_id": "event-review-1",
            "video_time_sec": 12.5,
            "primary_violation": "EYES_CLOSED",
            "severity": "MEDIUM",
            "risk_score": 4.0,
        },
    )
    violation_path = Path(tmp_path) / joined["session_id"] / "violations.jsonl"
    original_log = violation_path.read_text(encoding="utf-8")

    reviewed = client.put(
        f"/sessions/{joined['session_id']}/incidents/event-review-1",
        json={"status": "confirmed", "note": "Da doi chieu bang chung"},
        headers=headers,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "confirmed"
    assert reviewed.json()["reviewed_at"]
    assert violation_path.read_text(encoding="utf-8") == original_log

    listed = client.get(
        f"/sessions/{joined['session_id']}/incidents",
        headers=headers,
    )
    assert listed.status_code == 200
    assert [item["violation_event_id"] for item in listed.json()] == ["event-review-1"]

    with SessionLocal() as db:
        assert db.query(models.IncidentReview).count() == 1
