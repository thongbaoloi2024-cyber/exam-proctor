from datetime import datetime, timedelta, timezone
import random

from scripts.generate_report_dataset import (
    Config,
    SIGNAL_NAMES,
    _read_jsonl,
    make_session_evidence,
    snapshot_bytes,
    validate_session_evidence,
)


def test_generated_evidence_uses_real_fusion_contract(tmp_path):
    sessions_root = tmp_path / "sessions"
    config = Config(
        batch_id="unit-model-evidence",
        target_email="admin@example.edu.vn",
        exam_count=3,
        session_count=1,
        days=1,
        seed=42,
        org_admins=1,
        managers=2,
        proctors=1,
        snapshot_rate=0.0,
        sample_reports=0,
        report_formats=("html",),
        sessions_root=sessions_root,
        output_root=tmp_path / "output",
        password="Testing-password-123",
        dry_run=False,
        staff_domain="example.edu.vn",
        student_domain="student.example.edu.vn",
        exam_domain="lms.example.edu.vn",
        refresh_existing=False,
        regenerate_model_evidence=False,
    )
    started_at = datetime(2026, 8, 12, 8, 0, tzinfo=timezone.utc)
    payloads = {level: snapshot_bytes(level) for level in ("LOW", "MEDIUM", "HIGH")}

    _, violations, _, snapshots = make_session_evidence(
        config=config,
        rng=random.Random(2408),
        session_id="session-model-contract",
        student_name="Nguyễn Minh An",
        candidate_number="21010001",
        candidate_email="21010001@student.example.edu.vn",
        authentication_method="google",
        client_type="browser_extension",
        extension_version="1.2.0",
        profile="high",
        started_at=started_at,
        ended_at=started_at + timedelta(minutes=10),
        duration_sec=600.0,
        snapshot_payloads=payloads,
        desired_violation_count=8,
    )

    assert len(violations) == 8
    assert snapshots == 0
    evidence_counts = validate_session_evidence(sessions_root / "session-model-contract")
    assert evidence_counts["violations"] == 8

    signals = _read_jsonl(sessions_root / "session-model-contract" / "signals.jsonl")
    assert all("state" not in row for row in signals)
    assert {row["signal_name"] for row in signals} == set(SIGNAL_NAMES)

    transitions = _read_jsonl(
        sessions_root / "session-model-contract" / "state_transitions.jsonl"
    )
    assert any(
        row["scope"] == "signal"
        and row["from_state"] == "NORMAL"
        and row["to_state"] == "SUSPICIOUS"
        for row in transitions
    )
    assert not any(
        row["scope"] == "signal"
        and row["from_state"] == "NORMAL"
        and row["to_state"] == "ALERT"
        for row in transitions
    )
