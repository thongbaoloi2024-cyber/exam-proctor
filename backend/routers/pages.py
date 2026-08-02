"""Trang HTML server-rendered (Jinja2) cho dashboard giam thi (Tuan 14) -
xem docs/KE_HOACH_PLATFORM.md ly do chon Jinja2+vanilla JS thay vi React.

Cac route o day CHI tra ve khung HTML tinh - toan bo du lieu that (danh
sach exam, phien, vi pham...) duoc JS phia trinh duyet tu goi lai dung API
JSON da co san (`routers/auth.py`/`exams.py`/`sessions.py`/`ws.py`), dung
cookie HttpOnly. Vi vay cac route render trang KHONG can
`Depends(require_role(...))` - viec kiem tra quyen van xay ra o tang API JSON
khi JS goi toi, khong phai o buoc render khung trang.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(include_in_schema=False)

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/", response_class=RedirectResponse)
def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/exams")


@router.get("/ui/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {"hide_sidebar": True})


@router.get("/ui/register", response_class=HTMLResponse)
def register_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "register.html", {"hide_sidebar": True})


@router.get("/ui/exams", response_class=HTMLResponse)
def exams_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "exams.html")


@router.get("/ui/exams/{exam_id}/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, exam_id: str) -> HTMLResponse:
    return templates.TemplateResponse(request, "dashboard.html", {"exam_id": exam_id})


@router.get("/ui/exams/{exam_id}/sessions/{session_id}", response_class=HTMLResponse)
def session_detail_page(request: Request, exam_id: str, session_id: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "session_detail.html", {"exam_id": exam_id, "session_id": session_id},
    )
