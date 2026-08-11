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
            "exam_url": "https://exam.example/test",
            "require_extension": True,
            "require_microphone": True,
            "max_focus_loss_seconds": 2.5,
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["require_extension"] is True
    assert updated.json()["require_microphone"] is True
    assert updated.json()["max_focus_loss_seconds"] == 2.5

    readiness = client.get(
        f"/exams/{exam['id']}/readiness",
        headers=headers,
    )
    assert readiness.status_code == 200
    readiness_by_code = {item["code"]: item for item in readiness.json()["items"]}
    assert readiness_by_code["destination"]["ready"] is True
    assert readiness_by_code["staffing"]["ready"] is True

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


def test_exam_configuration_is_editable_only_without_live_sessions(client):
    _, token = _register_exam_owner(client, "editability-admin@test.local")
    headers = _headers(token)
    created = client.post(
        "/exams",
        json={"name": "Editable Open Exam"},
        headers=headers,
    )
    assert created.status_code == 201
    exam = created.json()

    readiness = client.get(f"/exams/{exam['id']}/readiness", headers=headers).json()
    assert readiness["active_sessions"] == 0
    assert readiness["configuration_editable"] is True

    updated = client.patch(
        f"/exams/{exam['id']}",
        json={"expected_version": exam["version"], "name": "Updated While Open"},
        headers=headers,
    )
    assert updated.status_code == 200
    current_version = updated.json()["version"]

    joined = client.post(
        "/exams/join",
        json={"join_code": exam["join_code"], "student_name": "Live Student"},
    )
    assert joined.status_code == 200
    session_id = joined.json()["session_id"]

    for live_status in ("pending", "active", "disconnected"):
        with SessionLocal() as db:
            exam_session = db.get(models.ExamSession, session_id)
            exam_session.status = live_status
            db.commit()
        blocked = client.patch(
            f"/exams/{exam['id']}",
            json={"expected_version": current_version, "name": f"Blocked {live_status}"},
            headers=headers,
        )
        assert blocked.status_code == 409
        assert "phien dang tham gia" in blocked.json()["detail"]

    readiness = client.get(f"/exams/{exam['id']}/readiness", headers=headers).json()
    assert readiness["active_sessions"] == 1
    assert readiness["configuration_editable"] is False

    with SessionLocal() as db:
        exam_session = db.get(models.ExamSession, session_id)
        exam_session.status = "ended"
        db.commit()

    updated_after_end = client.patch(
        f"/exams/{exam['id']}",
        json={"expected_version": current_version, "name": "Editable After End"},
        headers=headers,
    )
    assert updated_after_end.status_code == 200
    assert updated_after_end.json()["name"] == "Editable After End"

    closed = client.patch(
        f"/exams/{exam['id']}/status",
        json={"status": "closed", "expected_version": updated_after_end.json()["version"]},
        headers=headers,
    )
    assert closed.status_code == 200
    archived = client.patch(
        f"/exams/{exam['id']}/status",
        json={"status": "archived", "expected_version": closed.json()["version"]},
        headers=headers,
    )
    assert archived.status_code == 200
    archived_update = client.patch(
        f"/exams/{exam['id']}",
        json={"expected_version": archived.json()["version"], "name": "Archived Update"},
        headers=headers,
    )
    assert archived_update.status_code == 409

    archived_readiness = client.get(f"/exams/{exam['id']}/readiness", headers=headers).json()
    assert archived_readiness["active_sessions"] == 0
    assert archived_readiness["configuration_editable"] is False


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


def test_exam_pins_are_default_ordered_and_private_to_each_assignment(client):
    admin_token, owner_token = _register_exam_owner(client, "pins-admin@test.local")
    owner_headers = _headers(owner_token)
    first_exam = client.post(
        "/exams",
        json={"name": "First Pinned Exam"},
        headers=owner_headers,
    ).json()
    second_exam = client.post(
        "/exams",
        json={"name": "Newest Pinned Exam"},
        headers=owner_headers,
    ).json()
    assert first_exam["is_pinned"] is True
    assert first_exam["pinned_at"]
    assert second_exam["is_pinned"] is True

    owner_list = client.get("/exams", headers=owner_headers).json()
    assert [item["id"] for item in owner_list[:2]] == [second_exam["id"], first_exam["id"]]
    owner_pins = client.get("/exams/pinned", headers=owner_headers)
    assert owner_pins.status_code == 200
    assert [item["id"] for item in owner_pins.json()] == [second_exam["id"], first_exam["id"]]

    teacher_id, teacher_token = _create_teacher(
        client,
        admin_token,
        "pins-teacher@test.local",
    )
    assert client.put(
        f"/exams/{first_exam['id']}/assignments",
        json={"user_id": teacher_id, "assignment_role": "proctor"},
        headers=owner_headers,
    ).status_code == 200
    teacher_headers = _headers(teacher_token)
    assert client.get("/exams/pinned", headers=teacher_headers).json() == []

    teacher_pin = client.patch(
        f"/exams/{first_exam['id']}/pin",
        json={"is_pinned": True},
        headers=teacher_headers,
    )
    assert teacher_pin.status_code == 200
    assert teacher_pin.json()["is_pinned"] is True
    owner_unpin = client.patch(
        f"/exams/{first_exam['id']}/pin",
        json={"is_pinned": False},
        headers=owner_headers,
    )
    assert owner_unpin.status_code == 200
    assert owner_unpin.json()["pinned_at"] is None

    assert [item["id"] for item in client.get(
        "/exams/pinned",
        headers=owner_headers,
    ).json()] == [second_exam["id"]]
    assert [item["id"] for item in client.get(
        "/exams/pinned",
        headers=teacher_headers,
    ).json()] == [first_exam["id"]]


def test_exam_workspace_overview_adapts_to_per_exam_assignment(client):
    admin_token, owner_token = _register_exam_owner(client, "workspace-admin@test.local")
    owner_headers = _headers(owner_token)
    managed_exam = client.post(
        "/exams",
        json={"name": "Managed Workspace Exam"},
        headers=owner_headers,
    ).json()
    proctored_exam = client.post(
        "/exams",
        json={"name": "Proctored Workspace Exam"},
        headers=owner_headers,
    ).json()
    teacher_id, teacher_token = _create_teacher(
        client,
        admin_token,
        "workspace-teacher@test.local",
    )
    assert client.put(
        f"/exams/{managed_exam['id']}/assignments",
        json={"user_id": teacher_id, "assignment_role": "manager"},
        headers=owner_headers,
    ).status_code == 200
    assert client.put(
        f"/exams/{proctored_exam['id']}/assignments",
        json={"user_id": teacher_id, "assignment_role": "proctor"},
        headers=owner_headers,
    ).status_code == 200

    joined = client.post(
        "/exams/join",
        json={"join_code": proctored_exam["join_code"], "student_name": "Workspace Student"},
    ).json()
    with SessionLocal() as db:
        exam_session = db.get(models.ExamSession, joined["session_id"])
        exam_session.status = "disconnected"
        exam_session.session_state_current = "SESSION_ALERT"
        exam_session.integrity_status_current = "alert"
        db.commit()

    overview = client.get(
        "/exams/workspace/overview",
        headers=_headers(teacher_token),
    )
    assert overview.status_code == 200
    body = overview.json()
    assert body["assigned_exams_total"] == 2
    assert body["managed_exams"] == 1
    assert body["proctored_exams"] == 1
    assert body["active_sessions"] == 1
    assert body["disconnected_sessions"] == 1
    assert body["alert_sessions"] == 1
    by_name = {item["name"]: item for item in body["items"]}
    assert by_name["Managed Workspace Exam"]["assignment_role"] == "manager"
    assert "exam.manage" in by_name["Managed Workspace Exam"]["allowed_actions"]
    assert by_name["Proctored Workspace Exam"]["assignment_role"] == "proctor"
    assert "exam.manage" not in by_name["Proctored Workspace Exam"]["allowed_actions"]
    assert by_name["Proctored Workspace Exam"]["alert_sessions"] == 1

    assert client.get(
        "/exams/workspace/overview",
        headers=_headers(admin_token),
    ).status_code == 403


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

    queue = client.get(f"/exams/{exam['id']}/incidents", headers=headers)
    assert queue.status_code == 200
    assert queue.json()[0]["event_id"] == "event-review-1"
    assert queue.json()[0]["status"] == "confirmed"

    with SessionLocal() as db:
        assert db.query(models.IncidentReview).count() == 1


def test_manager_can_reset_failed_session_and_archive_previous_evidence(client, tmp_path, monkeypatch):
    monkeypatch.setattr(session_materializer, "SESSIONS_ROOT", tmp_path)
    admin_token, token = _register_exam_owner(client, "reset-admin@test.local")
    headers = _headers(token)
    exam = client.post("/exams", json={"name": "Reset Exam"}, headers=headers).json()
    joined = client.post(
        "/exams/join",
        json={"join_code": exam["join_code"], "student_name": "Reset Student"},
    ).json()
    session_materializer.append_jsonl(
        joined["session_id"],
        "violations.jsonl",
        {"event_id": "old-attempt", "video_time_sec": 1, "severity": "LOW"},
    )
    ended = client.post(
        f"/sessions/{joined['session_id']}/end",
        json={"reason": "Thiết bị gặp lỗi"},
        headers=headers,
    )
    assert ended.status_code == 200

    reset = client.post(
        f"/sessions/{joined['session_id']}/reset",
        json={"reason": "Cho phép thí sinh thử lại sau lỗi thiết bị"},
        headers=headers,
    )
    assert reset.status_code == 200
    assert reset.json()["status"] == "pending"
    assert reset.json()["reset_count"] == 1
    assert (tmp_path / ".reset_archives" / joined["session_id"] / "attempt-1" / "violations.jsonl").is_file()
    assert (tmp_path / joined["session_id"] / "violations.jsonl").read_text(encoding="utf-8") == ""

    audit = client.get(
        "/organizations/current/audit?search=exam.session.reset",
        headers=_headers(admin_token),
    )
    assert audit.status_code == 200
    assert audit.json()[0]["reason"] == "Cho phép thí sinh thử lại sau lỗi thiết bị"
