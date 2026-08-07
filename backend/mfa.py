"""Dependency-free TOTP plus encrypted secret and one-use recovery codes."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from io import BytesIO
import os
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
import qrcode

from .auth import SECRET_KEY


def _fernet() -> Fernet:
    configured = os.environ.get("MFA_ENCRYPTION_KEY", "").strip()
    if configured:
        try:
            return Fernet(configured.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise RuntimeError("MFA_ENCRYPTION_KEY phai la Fernet key hop le") from exc
    if os.environ.get("APP_ENV", "development").strip().lower() == "production":
        raise RuntimeError("Production bat buoc dat MFA_ENCRYPTION_KEY")
    derived = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode("utf-8")).digest())
    return Fernet(derived)


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode("ascii")).decode("ascii")
    except InvalidToken as exc:
        raise ValueError("Khong giai ma duoc MFA secret") from exc


def _totp(secret: str, counter: int) -> str:
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{binary % 1_000_000:06d}"


def verify_totp(secret: str, code: str, *, now: float | None = None) -> bool:
    if not code.isdigit() or len(code) != 6:
        return False
    counter = int((time.time() if now is None else now) // 30)
    return any(hmac.compare_digest(_totp(secret, counter + drift), code) for drift in (-1, 0, 1))


def current_totp(secret: str, *, now: float | None = None) -> str:
    return _totp(secret, int((time.time() if now is None else now) // 30))


def provisioning_uri(secret: str, email: str) -> str:
    label = quote(f"DATT:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer=DATT&digits=6&period=30"


def qr_code_data_url(value: str) -> str:
    """Return a self-contained PNG QR code without sending its value elsewhere."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def generate_recovery_codes(count: int = 8) -> tuple[list[str], str]:
    raw_codes = [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(count)]
    hashes = [hashlib.sha256(code.encode("utf-8")).hexdigest() for code in raw_codes]
    return raw_codes, json.dumps(hashes)


def consume_recovery_code(stored_json: str | None, code: str) -> tuple[bool, str | None]:
    if not stored_json:
        return False, stored_json
    try:
        hashes = json.loads(stored_json)
    except (TypeError, ValueError):
        return False, stored_json
    candidate = hashlib.sha256(code.strip().casefold().encode("utf-8")).hexdigest()
    for index, stored_hash in enumerate(hashes):
        if hmac.compare_digest(stored_hash, candidate):
            hashes.pop(index)
            return True, json.dumps(hashes)
    return False, stored_json
