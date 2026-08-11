"""Background report queue integration test."""
from __future__ import annotations

import backend.session_materializer as session_materializer
from backend.tests.helpers import register_org_with_exam_manager
from scripts.report_worker import process_one


def test_report_job_is_queued_processed_and_queryable(client, tmp_path, monkeypatch):
    monkeypatch.setattr(session_materializer, "SESSIONS_ROOT", tmp_path)
    _, token, _ = register_org_with_exam_manager(
        client,
        admin_email="report-worker@test.local",
        organization_name="Report Worker Org",
    )
    headers = {"Authorization": f"Bearer {token}"}
    exam = client.post("/exams", json={"name": "Report Job Exam"}, headers=headers).json()
    joined = client.post(
        "/exams/join",
        json={"join_code": exam["join_code"], "student_name": "Report Student"},
    ).json()
    session_materializer.ensure_session_dir(joined["session_id"])

    queued = client.post(
        f"/sessions/{joined['session_id']}/report-jobs/html",
        headers=headers,
    )
    assert queued.status_code == 202
    assert queued.json()["status"] == "pending"
    assert process_one() is True

    completed = client.get(
        f"/report-jobs/{queued.json()['id']}",
        headers=headers,
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert (tmp_path / joined["session_id"] / "report.html").is_file()
    download = client.get(
        f"/report-jobs/{queued.json()['id']}/download",
        headers=headers,
    )
    assert download.status_code == 200
    assert "text/html" in download.headers["content-type"]
