"""Apply per-organization retention. Dry-run unless ``--apply`` is passed."""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timedelta, timezone

from backend import models
from backend.audit import record_audit
from backend.db import Base, SessionLocal, engine
from backend.db_migrations import apply_additive_migrations
from backend.session_materializer import SESSIONS_ROOT, session_dir_for


def eligible_sessions(db):
    rows = (
        db.query(models.ExamSession, models.Exam, models.Organization)
        .join(models.Exam, models.Exam.id == models.ExamSession.exam_id)
        .join(models.Organization, models.Organization.id == models.Exam.org_id)
        .filter(models.ExamSession.ended_at.is_not(None))
        .all()
    )
    now = datetime.now(timezone.utc)
    eligible = []
    for exam_session, exam, organization in rows:
        ended_at = exam_session.ended_at
        if ended_at is None:
            continue
        ended_at = ended_at.replace(tzinfo=ended_at.tzinfo or timezone.utc)
        if ended_at <= now - timedelta(days=organization.retention_days):
            eligible.append((exam_session, exam, organization))
    return eligible


def remove_session_files(session_id: str) -> None:
    root = SESSIONS_ROOT.resolve()
    target = session_dir_for(session_id).resolve()
    if target.parent != root or target == root:
        raise RuntimeError(f"Unsafe retention path: {target}")
    if target.is_dir():
        shutil.rmtree(target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete expired evidence and anonymize session rows")
    parser.add_argument("--apply", action="store_true", help="Actually delete; default is dry-run")
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    apply_additive_migrations(engine)
    with SessionLocal() as db:
        rows = eligible_sessions(db)
        for exam_session, exam, organization in rows:
            print(f"{exam_session.id} org={organization.id} ended={exam_session.ended_at}")
            if not args.apply:
                continue
            remove_session_files(exam_session.id)
            db.query(models.IncidentReview).filter_by(exam_session_id=exam_session.id).delete()
            db.query(models.ReportJob).filter_by(exam_session_id=exam_session.id).delete()
            exam_session.student_name = "[retention-deleted]"
            exam_session.candidate_number = None
            exam_session.candidate_email = None
            exam_session.candidate_identity_id = None
            exam_session.device_id_hash = None
            exam_session.browser_name = None
            exam_session.disconnect_reason = "retention_deleted"
            record_audit(
                db,
                actor=None,
                action="system.retention.apply",
                resource_type="exam_session",
                resource_id=exam_session.id,
                org_id=organization.id,
                exam_id=exam.id,
                after={"evidence_deleted": True, "identity_anonymized": True},
            )
        if args.apply:
            db.commit()
    print(f"Eligible sessions: {len(rows)}; mode={'apply' if args.apply else 'dry-run'}")


if __name__ == "__main__":
    main()

