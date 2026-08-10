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
    from .auth import web_google_oauth_configured

    return templates.TemplateResponse(
        request,
        "login.html",
        {"hide_sidebar": True, "google_oauth_enabled": web_google_oauth_configured()},
    )


@router.get("/ui/register", response_class=HTMLResponse)
def register_page(request: Request) -> HTMLResponse:
    from .auth import web_google_oauth_configured

    return templates.TemplateResponse(
        request,
        "register.html",
        {"hide_sidebar": True, "google_oauth_enabled": web_google_oauth_configured()},
    )


@router.get("/ui/register/organization", response_class=HTMLResponse)
def google_organization_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "register_organization.html",
        {"hide_sidebar": True},
    )


@router.get("/ui/mfa", response_class=HTMLResponse)
def mfa_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "mfa.html", {"hide_sidebar": True})


@router.get("/ui/mfa/verify", response_class=HTMLResponse)
def mfa_verify_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "mfa_verify.html", {"hide_sidebar": True})


@router.get("/ui/exams", response_class=HTMLResponse)
def exams_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "exams.html")


@router.get("/ui/organization", response_class=HTMLResponse)
def organization_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "organization.html")


@router.get("/ui/system", response_class=HTMLResponse)
def system_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "system.html")


@router.get("/ui/system/organizations", response_class=HTMLResponse)
def system_organizations_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "system_organizations.html")


@router.get("/ui/system/organizations/{organization_id}", response_class=HTMLResponse)
def system_organization_detail_page(request: Request, organization_id: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "system_organization_detail.html",
        {"organization_id": organization_id},
    )


@router.get("/ui/system/security", response_class=HTMLResponse)
def system_security_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "system_security.html")


@router.get("/ui/system/evidence", response_class=HTMLResponse)
def system_evidence_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "exams.html",
        {"system_evidence": True},
    )


@router.get("/ui/system/audit", response_class=HTMLResponse)
def system_audit_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "system_audit.html")


@router.get("/ui/exams/{exam_id}/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, exam_id: str) -> HTMLResponse:
    return templates.TemplateResponse(request, "dashboard.html", {"exam_id": exam_id})


@router.get("/ui/exams/{exam_id}/manage", response_class=HTMLResponse)
def exam_manage_page(request: Request, exam_id: str) -> HTMLResponse:
    return templates.TemplateResponse(request, "exam_manage.html", {"exam_id": exam_id})


@router.get("/ui/exams/{exam_id}/sessions/{session_id}", response_class=HTMLResponse)
def session_detail_page(request: Request, exam_id: str, session_id: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "session_detail.html", {"exam_id": exam_id, "session_id": session_id},
    )
