"""FastAPI entry point cho platform multi-tenant.

Chay development tu repository root sau khi cai ``requirements-backend.txt``:
``uvicorn backend.main:app --reload``. Backend dung SQLite cuc bo khi khong co
cau hinh DB; production bat buoc cung cap Postgres/secret qua environment.
"""
from __future__ import annotations

import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .db import Base, engine
from .db_migrations import apply_additive_migrations
from .routers import auth as auth_router
from .routers import candidate_auth as candidate_auth_router
from .routers import exams as exams_router
from .routers import organizations as organizations_router
from .routers import pages as pages_router
from .routers import sessions as sessions_router
from .routers import system as system_router
from .routers import ws as ws_router

_IS_PRODUCTION = os.environ.get("APP_ENV", "development").strip().lower() == "production"
_allowed_hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "*").split(",") if h.strip()]


def initialize_backend() -> None:
    """Validate the deployment shape and prepare the database."""
    if _IS_PRODUCTION and (not _allowed_hosts or "*" in _allowed_hosts):
        raise RuntimeError("Production bat buoc dat ALLOWED_HOSTS cu the, khong dung '*'")
    try:
        worker_count = int(os.environ.get("WEB_CONCURRENCY", "1"))
    except ValueError as exc:
        raise RuntimeError("WEB_CONCURRENCY phai la so nguyen") from exc
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if worker_count != 1 and not redis_url:
        raise RuntimeError(
            "Nhieu backend worker bat buoc cau hinh REDIS_URL cho pub/sub, "
            "client lease va distributed rate limit."
        )
    candidate_auth_router.validate_google_oauth_configuration()
    auth_router.validate_web_google_oauth_configuration()
    Base.metadata.create_all(bind=engine)
    apply_additive_migrations(engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_backend()
    yield


app = FastAPI(
    title="DATT Exam Proctoring Platform",
    docs_url=None if _IS_PRODUCTION else "/docs",
    redoc_url=None if _IS_PRODUCTION else "/redoc",
    lifespan=lifespan,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts or ["*"])

_extension_origins = [
    origin.strip()
    for origin in os.environ.get("EXTENSION_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if _extension_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_extension_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    force_https = os.environ.get("FORCE_HTTPS", "false").strip().lower() in {"1", "true", "yes", "on"}
    if force_https and request.url.scheme != "https":
        return RedirectResponse(str(request.url.replace(scheme="https")), status_code=307)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    host = request.url.netloc
    websocket_sources = f"ws://{host} wss://{host}" if re.fullmatch(r"[A-Za-z0-9.:\[\]-]+", host) else ""
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        f"img-src 'self' data: blob: https:; connect-src 'self' {websocket_sources}; object-src 'none'; "
        "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith(
        ("/auth", "/system", "/organizations", "/exams", "/sessions", "/ui")
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

app.include_router(auth_router.router)
app.include_router(candidate_auth_router.router)
app.include_router(exams_router.router)
app.include_router(organizations_router.router)
app.include_router(sessions_router.router)
app.include_router(system_router.router)
app.include_router(ws_router.router)
app.include_router(pages_router.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
