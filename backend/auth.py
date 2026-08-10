"""Bam mat khau + JWT cho User (admin/proctor), va 1 loai token rieng, nhe
hon cho ExamSession (thi sinh) dung de xac thuc ket noi WebSocket
(`/ws/client` voi header Authorization cho desktop hoac ve mot-lan cho
browser extension, xem routers/ws.py) - tach rieng vi ExamSession
khong phai User, khong co role/mat khau.
"""
from __future__ import annotations

import os
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models
from .db import get_db
from .ws_tickets import ticket_store

AUTH_COOKIE_NAME = "datt_access_token"
AUTH_FLOW_COOKIE_NAME = "datt_auth_flow"


def _load_secret_key() -> str:
    configured = os.environ.get("JWT_SECRET_KEY", "").strip()
    environment = os.environ.get("APP_ENV", "development").strip().lower()
    if configured:
        if environment == "production" and len(configured) < 32:
            raise RuntimeError("JWT_SECRET_KEY phai co it nhat 32 ky tu trong production")
        return configured
    if environment == "production":
        raise RuntimeError("Bat buoc dat JWT_SECRET_KEY khi APP_ENV=production")
    warnings.warn(
        "JWT_SECRET_KEY chua duoc dat; dang dung secret ngau nhien tam thoi cho development.",
        RuntimeWarning,
        stacklevel=2,
    )
    return secrets.token_urlsafe(48)


SECRET_KEY = _load_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12
SESSION_TOKEN_EXPIRE_HOURS = 6

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=_env_flag("COOKIE_SECURE", os.environ.get("APP_ENV") == "production"),
        samesite="strict",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/", samesite="strict")


def set_auth_flow_cookie(response: Response, token: str, max_age: int = 600) -> None:
    response.set_cookie(
        key=AUTH_FLOW_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=_env_flag("COOKIE_SECURE", os.environ.get("APP_ENV") == "production"),
        samesite="lax",
        path="/",
    )


def clear_auth_flow_cookie(response: Response) -> None:
    response.delete_cookie(key=AUTH_FLOW_COOKIE_NAME, path="/", samesite="lax")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


# --- User JWT (admin/proctor) ------------------------------------------------


def create_access_token(
    user_id: str,
    role: str,
    org_id: str,
    session_version: int = 1,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "role": role,
        "org_id": org_id,
        "ver": session_version,
        "type": "user",
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    request: Request,
    bearer_token: Optional[str] = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Khong xac thuc duoc token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = bearer_token or request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise credentials_error
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "user":
            raise credentials_error
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.get(models.User, user_id)
    token_version = payload.get("ver", 1)
    token_org_id = payload.get("org_id")
    if (
        user is None
        or user.status != "active"
        or token_version != user.session_version
        or not isinstance(token_org_id, str)
    ):
        raise credentials_error
    membership = db.query(models.OrganizationMembership).filter_by(
        user_id=user.id,
        org_id=token_org_id,
        status="active",
    ).first()
    organization = db.get(models.Organization, token_org_id)
    if membership is None or organization is None or organization.status != "active":
        raise credentials_error
    user._authorization_org_id = token_org_id
    return user


def require_role(*allowed_roles: str):
    def _dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Khong du quyen")
        return user

    return _dependency


# --- Session token (thi sinh, dung cho WS client) ----------------------------


def create_session_token(session_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=SESSION_TOKEN_EXPIRE_HOURS)
    payload = {"sub": session_id, "type": "exam_session", "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_session_token(token: str) -> str:
    """Tra ve session_id neu token hop le, nem HTTPException neu khong."""
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session_token khong hop le")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise error
    if payload.get("type") != "exam_session":
        raise error
    session_id = payload.get("sub")
    if not session_id:
        raise error
    return session_id


def decode_user_token_for_ws(token: str, db: Session) -> models.User:
    """Ban tuong duong get_current_user() nhung goi truc tiep (khong qua
    Depends/OAuth2PasswordBearer) - dung trong WebSocket endpoint
    (`/ws/dashboard/{exam_id}`) voi cookie HttpOnly hoac Authorization."""
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Khong xac thuc duoc token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "user":
            raise error
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise error
    except JWTError:
        raise error

    user = db.get(models.User, user_id)
    token_version = payload.get("ver", 1)
    token_org_id = payload.get("org_id")
    if (
        user is None
        or user.status != "active"
        or token_version != user.session_version
        or not isinstance(token_org_id, str)
    ):
        raise error
    membership = db.query(models.OrganizationMembership).filter_by(
        user_id=user.id,
        org_id=token_org_id,
        status="active",
    ).first()
    organization = db.get(models.Organization, token_org_id)
    if membership is None or organization is None or organization.status != "active":
        raise error
    user._authorization_org_id = token_org_id
    return user


def _bearer_from_websocket(websocket: WebSocket) -> Optional[str]:
    authorization = websocket.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value:
        return value.strip()
    return None


def decode_session_websocket(websocket: WebSocket) -> str:
    token = _bearer_from_websocket(websocket)
    if token:
        websocket.state.auth_subprotocol = None
        return decode_session_token(token)

    requested_protocols = [
        item.strip() for item in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if item.strip()
    ]
    ticket_protocol = next(
        (item for item in requested_protocols if item.startswith("ticket.")), None,
    )
    if "datt-v1" not in requested_protocols or ticket_protocol is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Thieu ve WebSocket")
    session_id = ticket_store.consume(ticket_protocol.removeprefix("ticket."))
    if session_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ve WebSocket khong hop le")
    websocket.state.auth_subprotocol = "datt-v1"
    return session_id


def decode_user_websocket(websocket: WebSocket, db: Session) -> models.User:
    token = _bearer_from_websocket(websocket) or websocket.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Thieu access token")
    return decode_user_token_for_ws(token, db)
