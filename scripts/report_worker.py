"""Database-backed report worker for production/offline deployments."""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend import models
from backend.db import Base, SessionLocal, engine
from backend.db_migrations import apply_additive_migrations
from backend.session_materializer import session_dir_for
from src.reporting.report_generator import generate_report

_FUSION_CONFIG = Path(__file__).resolve().parents[1] / "config" / "fusion.yaml"


def process_one() -> bool:
    with SessionLocal() as db:
        job = (
            db.query(models.ReportJob)
            .filter(models.ReportJob.status == "pending")
            .order_by(models.ReportJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if job is None:
            return False
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        job_id = job.id
        session_id = job.exam_session_id
        fmt = job.format

    try:
        output = generate_report(
            session_dir_for(session_id),
            fusion_config_path=str(_FUSION_CONFIG),
            formats=[fmt],
        )[fmt]
        with SessionLocal() as db:
            job = db.get(models.ReportJob, job_id)
            if job is not None:
                job.status = "completed"
                job.output_path = str(output)
                job.completed_at = datetime.now(timezone.utc)
                job.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
                db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            job = db.get(models.ReportJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)[:1000]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Process queued report jobs")
    parser.add_argument("--once", action="store_true", help="Exit after one poll")
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    apply_additive_migrations(engine)
    while True:
        processed = process_one()
        if args.once:
            return
        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    main()

