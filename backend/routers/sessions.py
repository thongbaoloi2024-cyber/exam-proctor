"""REST cho quan ly phien: danh sach phien cua 1 ky thi (tai ban dau cho
dashboard truoc khi nhan cap nhat qua WebSocket), ket thuc phien, va tai bao
cao cuoi phien - tai dung src/reporting/generate_report() nguyen ban, KHONG
doi gi trong src/reporting/ (chi dung dung shape thu muc, xem
session_materializer.py).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path as _Path

from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .. import models
from ..auth import decode_session_token, get_current_user
from ..authorization import Permission, authorize_exam, authorize_session
from ..audit import record_audit
from ..candidate_tokens import bearer_token_from_request
from ..db import get_db
from ..session_materializer import build_session_meta, session_dir_for, write_session_meta
from ..ws_tickets import ticket_store

# src/reporting/ nam o repo root, ngoai package backend/ - them root vao
# sys.path de import lai dung module CV da co (Tuan 11), khong copy/viet lai
# logic sinh bao cao.
_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.reporting.data_loader import load_session_report_data  # noqa: E402
from src.reporting.report_generator import generate_report  # noqa: E402

router = APIRouter(tags=["sessions"])

_FUSION_CONFIG_PATH = _REPO_ROOT / "config" / "fusion.yaml"


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    student_name: str
    candidate_number: str | None
    candidate_email: str | None
    authentication_method: str
    client_type: str
    extension_version: str | None
    browser_name: str | None
    status: str
    risk_score_current: float
    session_state_current: str
    last_seen_at: datetime | None
    disconnect_reason: str | None
    integrity_score_current: float
    integrity_status_current: str
    browser_event_count: int


class WebSocketTicketResponse(BaseModel):
    ticket: str
    subprotocol: str = "datt-v1"
    expires_in_seconds: int = 30


class IncidentReviewRequest(BaseModel):
    status: Literal["new", "in_review", "confirmed", "dismissed"]
    note: str | None = Field(default=None, max_length=5000)


class IncidentReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    exam_session_id: str
    violation_event_id: str
    status: str
    note: str | None
    reviewed_by_user_id: str | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None


class ReportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    exam_session_id: str
    format: str
    status: str
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None

@router.get("/exams/{exam_id}/sessions", response_model=list[SessionResponse])
def list_sessions(
    exam_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[models.ExamSession]:
    authorize_exam(db, user, exam_id, Permission.EXAM_MONITOR)
    sessions = db.query(models.ExamSession).filter(models.ExamSession.exam_id == exam_id).all()
    now = datetime.now(timezone.utc)
    changed = False
    for exam_session in sessions:
        started_at = exam_session.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if exam_session.status == "pending" and (now - started_at).total_seconds() > 60.0:
            exam_session.status = "disconnected"
            exam_session.disconnect_reason = "client_never_connected"
            changed = True
    if changed:
        db.commit()
    return sessions


@router.post("/sessions/{session_id}/ws-ticket", response_model=WebSocketTicketResponse)
def create_websocket_ticket(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> WebSocketTicketResponse:
    """Mint a one-use ticket for browser WebSocket APIs.

    The real session JWT stays in the REST Authorization header.  The returned
    random ticket is valid for 30 seconds and is consumed on first WS attempt.
    """
    raw_session_token = bearer_token_from_request(request)
    if raw_session_token is None or decode_session_token(raw_session_token) != session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session token khong hop le")
    exam_session = db.get(models.ExamSession, session_id)
    if exam_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay phien")
    if exam_session.status == "ended":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phien da ket thuc")
    if exam_session.client_type != "browser_extension":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ve chi danh cho browser extension")
    return WebSocketTicketResponse(ticket=ticket_store.issue(session_id))


@router.post("/sessions/{session_id}/end", response_model=SessionResponse)
def end_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.ExamSession:
    """Giam thi/admin ket thuc HO 1 phien (VD thi sinh mat ket noi, khong tu
    ket thuc duoc). Luong binh thuong la chinh thi sinh tu ket thuc qua
    message "end_session" tren WebSocket dang dung (`routers/ws.py`) - noi
    do dung chung `build_session_meta()` voi endpoint nay de tranh lech."""
    exam_session = authorize_session(
        db,
        user,
        session_id,
        Permission.EXAM_SESSIONS_END,
    )

    if exam_session.status != "ended":
        exam_session.status = "ended"
        exam_session.ended_at = datetime.now(timezone.utc)
        exam_session.disconnect_reason = "ended_by_proctor"
    record_audit(
        db,
        actor=user,
        action="exam.session.end",
        resource_type="exam_session",
        resource_id=exam_session.id,
        org_id=exam_session.exam.org_id,
        exam_id=exam_session.exam_id,
        request=request,
    )
    db.commit()
    db.refresh(exam_session)

    write_session_meta(
        session_id,
        build_session_meta(
            session_id,
            exam_session.started_at,
            exam_session.ended_at,
            end_reason="ended_by_proctor",
            student_name=exam_session.student_name,
            candidate_number=exam_session.candidate_number,
            candidate_email=exam_session.candidate_email,
            authentication_method=exam_session.authentication_method,
            client_type=exam_session.client_type,
            extension_version=exam_session.extension_version,
        ),
    )
    return exam_session


@router.get("/sessions/{session_id}/detail")
def get_session_detail(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Du lieu cho trang chi tiet 1 phien tren dashboard (Tuan 14) - tai
    dung `load_session_report_data()` (Tuan 11, `src/reporting/`) thay vi tu
    doc lai `violations.jsonl`/`session_meta.json` rieng, tranh 2 noi cung
    parse 1 dinh dang JSONL ma co the lech nhau."""
    exam_session = authorize_session(
        db,
        user,
        session_id,
        Permission.EXAM_EVIDENCE_READ,
    )

    data = load_session_report_data(session_dir_for(session_id))
    record_audit(
        db,
        actor=user,
        action="exam.evidence.view",
        resource_type="exam_session",
        resource_id=exam_session.id,
        org_id=exam_session.exam.org_id,
        exam_id=exam_session.exam_id,
        request=request,
    )
    db.commit()
    return {
        "session_id": session_id,
        "student_name": exam_session.student_name,
        "status": exam_session.status,
        "candidate_number": exam_session.candidate_number,
        "candidate_email": exam_session.candidate_email,
        "authentication_method": exam_session.authentication_method,
        "client_type": exam_session.client_type,
        "extension_version": exam_session.extension_version,
        "browser_name": exam_session.browser_name,
        "integrity_score": exam_session.integrity_score_current,
        "integrity_status": exam_session.integrity_status_current,
        "browser_event_count": exam_session.browser_event_count,
        "session_meta": data.session_meta,
        "violations": sorted(data.violations, key=lambda v: v.get("video_time_sec", 0)),
        "browser_events": sorted(data.browser_events, key=lambda v: v.get("video_time_sec", 0)),
        "risk_timeline": data.risk_timeline,
    }


@router.get(
    "/sessions/{session_id}/incidents",
    response_model=list[IncidentReviewResponse],
)
def list_incident_reviews(
    session_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[models.IncidentReview]:
    exam_session = authorize_session(db, user, session_id, Permission.EXAM_INCIDENT_REVIEW)
    return (
        db.query(models.IncidentReview)
        .filter(models.IncidentReview.exam_session_id == session_id)
        .order_by(models.IncidentReview.updated_at.desc())
        .all()
    )


@router.put(
    "/sessions/{session_id}/incidents/{event_id}",
    response_model=IncidentReviewResponse,
)
def review_incident(
    session_id: str,
    event_id: str,
    payload: IncidentReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.IncidentReview:
    exam_session = authorize_session(
        db,
        user,
        session_id,
        Permission.EXAM_INCIDENT_REVIEW,
    )
    report_data = load_session_report_data(session_dir_for(session_id))
    if not any(str(item.get("event_id")) == event_id for item in report_data.violations):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay su co")
    review = db.query(models.IncidentReview).filter_by(
        exam_session_id=session_id,
        violation_event_id=event_id,
    ).first()
    now = datetime.now(timezone.utc)
    if review is None:
        review = models.IncidentReview(
            exam_session_id=session_id,
            violation_event_id=event_id,
        )
        db.add(review)
    review.status = payload.status
    review.note = payload.note.strip() if payload.note and payload.note.strip() else None
    review.reviewed_by_user_id = user.id
    review.reviewed_at = now if payload.status in {"confirmed", "dismissed"} else None
    review.updated_at = now
    db.flush()
    record_audit(
        db,
        actor=user,
        action="exam.incident.review",
        resource_type="incident_review",
        resource_id=review.id,
        org_id=exam_session.exam.org_id,
        exam_id=exam_session.exam_id,
        request=request,
        after={"event_id": event_id, "status": review.status, "note": review.note},
    )
    db.commit()
    db.refresh(review)
    return review


@router.get("/sessions/{session_id}/snapshots/{filename}")
def get_snapshot(
    session_id: str,
    filename: str,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> FileResponse:
    """Phuc vu 1 anh chup bang chung (`snapshot_path` trong 1 `ViolationEvent`)
    de trang chi tiet phien hien thi truc tiep - `filename` chi lay ten file
    (khong nhan duong dan) roi ghep lai voi `session_dir_for()`, tranh path
    traversal ra ngoai thu muc phien cua chinh no."""
    exam_session = authorize_session(db, user, session_id, Permission.EXAM_EVIDENCE_READ)

    safe_filename = _Path(filename).name
    if safe_filename != filename or _Path(safe_filename).suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay anh chup")
    session_root = session_dir_for(session_id).resolve()
    unresolved_root = session_dir_for(session_id) / "snapshots"
    if unresolved_root.is_symlink():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay anh chup")
    snapshot_root = unresolved_root.resolve()
    if snapshot_root.parent != session_root:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay anh chup")
    unresolved = snapshot_root / safe_filename
    if unresolved.is_symlink():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay anh chup")
    snapshot_path = unresolved.resolve()
    if (
        snapshot_path.parent != snapshot_root
        or not snapshot_path.is_file()
        or snapshot_path.stat().st_size > 2 * 1024 * 1024
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay anh chup")
    media_type = "image/png" if snapshot_path.suffix.lower() == ".png" else "image/jpeg"
    record_audit(
        db,
        actor=user,
        action="exam.evidence.snapshot.view",
        resource_type="snapshot",
        resource_id=safe_filename,
        org_id=exam_session.exam.org_id,
        exam_id=exam_session.exam_id,
        request=request,
    )
    db.commit()
    return FileResponse(snapshot_path, media_type=media_type)


@router.get("/sessions/{session_id}/report/{fmt}")
def get_report(
    session_id: str,
    fmt: str,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> FileResponse:
    if fmt not in ("html", "pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fmt phai la html hoac pdf")

    exam_session = authorize_session(db, user, session_id, Permission.EXAM_REPORTS_EXPORT)

    session_dir = session_dir_for(session_id)
    paths = generate_report(
        session_dir, fusion_config_path=str(_FUSION_CONFIG_PATH), formats=[fmt],
    )
    record_audit(
        db,
        actor=user,
        action="exam.report.export",
        resource_type="exam_session_report",
        resource_id=f"{session_id}:{fmt}",
        org_id=exam_session.exam.org_id,
        exam_id=exam_session.exam_id,
        request=request,
    )
    db.commit()
    return FileResponse(paths[fmt])


@router.post(
    "/sessions/{session_id}/report-jobs/{fmt}",
    response_model=ReportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_report_job(
    session_id: str,
    fmt: str,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.ReportJob:
    if fmt not in ("html", "pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fmt phai la html hoac pdf")
    exam_session = authorize_session(db, user, session_id, Permission.EXAM_REPORTS_EXPORT)
    existing = db.query(models.ReportJob).filter_by(
        exam_session_id=session_id,
        format=fmt,
        status="pending",
    ).first()
    if existing is not None:
        return existing
    job = models.ReportJob(
        exam_session_id=session_id,
        requested_by_user_id=user.id,
        format=fmt,
        status="pending",
    )
    db.add(job)
    db.flush()
    record_audit(
        db,
        actor=user,
        action="exam.report.job.create",
        resource_type="report_job",
        resource_id=job.id,
        org_id=exam_session.exam.org_id,
        exam_id=exam_session.exam_id,
        request=request,
        after={"format": fmt, "status": "pending"},
    )
    db.commit()
    db.refresh(job)
    return job


@router.get("/report-jobs/{job_id}", response_model=ReportJobResponse)
def get_report_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.ReportJob:
    job = db.get(models.ReportJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay report job")
    authorize_session(db, user, job.exam_session_id, Permission.EXAM_REPORTS_EXPORT)
    return job
