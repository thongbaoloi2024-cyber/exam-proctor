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

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from .. import models
from ..auth import decode_session_token, require_role
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

def _get_owned_exam(db: Session, exam_id: str, user: models.User) -> models.Exam:
    exam = db.get(models.Exam, exam_id)
    if exam is None or exam.org_id != user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay ky thi")
    return exam


def _get_owned_session(db: Session, session_id: str, user: models.User) -> models.ExamSession:
    exam_session = db.get(models.ExamSession, session_id)
    if exam_session is None or exam_session.exam.org_id != user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Khong tim thay phien")
    return exam_session


@router.get("/exams/{exam_id}/sessions", response_model=list[SessionResponse])
def list_sessions(
    exam_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("admin", "proctor")),
) -> list[models.ExamSession]:
    _get_owned_exam(db, exam_id, user)
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
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("admin", "proctor")),
) -> models.ExamSession:
    """Giam thi/admin ket thuc HO 1 phien (VD thi sinh mat ket noi, khong tu
    ket thuc duoc). Luong binh thuong la chinh thi sinh tu ket thuc qua
    message "end_session" tren WebSocket dang dung (`routers/ws.py`) - noi
    do dung chung `build_session_meta()` voi endpoint nay de tranh lech."""
    exam_session = _get_owned_session(db, session_id, user)

    if exam_session.status != "ended":
        exam_session.status = "ended"
        exam_session.ended_at = datetime.now(timezone.utc)
        exam_session.disconnect_reason = "ended_by_proctor"
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
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("admin", "proctor")),
) -> Dict[str, Any]:
    """Du lieu cho trang chi tiet 1 phien tren dashboard (Tuan 14) - tai
    dung `load_session_report_data()` (Tuan 11, `src/reporting/`) thay vi tu
    doc lai `violations.jsonl`/`session_meta.json` rieng, tranh 2 noi cung
    parse 1 dinh dang JSONL ma co the lech nhau."""
    exam_session = _get_owned_session(db, session_id, user)

    data = load_session_report_data(session_dir_for(session_id))
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


@router.get("/sessions/{session_id}/snapshots/{filename}")
def get_snapshot(
    session_id: str,
    filename: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("admin", "proctor")),
) -> FileResponse:
    """Phuc vu 1 anh chup bang chung (`snapshot_path` trong 1 `ViolationEvent`)
    de trang chi tiet phien hien thi truc tiep - `filename` chi lay ten file
    (khong nhan duong dan) roi ghep lai voi `session_dir_for()`, tranh path
    traversal ra ngoai thu muc phien cua chinh no."""
    _get_owned_session(db, session_id, user)

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
    return FileResponse(snapshot_path, media_type=media_type)


@router.get("/sessions/{session_id}/report/{fmt}")
def get_report(
    session_id: str,
    fmt: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("admin", "proctor")),
) -> FileResponse:
    if fmt not in ("html", "pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fmt phai la html hoac pdf")

    _get_owned_session(db, session_id, user)

    session_dir = session_dir_for(session_id)
    paths = generate_report(
        session_dir, fusion_config_path=str(_FUSION_CONFIG_PATH), formats=[fmt],
    )
    return FileResponse(paths[fmt])
