"""JWT and password helpers.

This module keeps token handling self-contained so local verification can run
even when external JWT packages are unavailable in the current environment.
"""

from __future__ import annotations

import base64
import bcrypt
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from config.settings import settings


class JWTError(Exception):
    """Raised when a token is invalid or expired."""


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _sign(message: bytes) -> str:
    signature = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).digest()
    return _b64url_encode(signature)


def _build_token(
    subject: str,
    *,
    expires_delta: timedelta,
    token_type: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    header = {"alg": settings.JWT_ALGORITHM, "typ": "JWT"}
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    encoded_header = _b64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    encoded_payload = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    return f"{encoded_header}.{encoded_payload}.{_sign(signing_input)}"


def create_access_token(subject: str, *, role: str | None = None) -> str:
    claims = {"role": role} if role else None
    return _build_token(
        subject,
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
        extra_claims=claims,
    )


def create_refresh_token(subject: str) -> str:
    return _build_token(
        subject,
        expires_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise JWTError("Malformed token") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(encoded_signature, expected_signature):
        raise JWTError("Invalid token signature")

    try:
        payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
    except Exception as exc:
        raise JWTError("Invalid token payload") from exc

    now_ts = int(datetime.now(timezone.utc).timestamp())
    exp = int(payload.get("exp", 0))
    if exp <= now_ts:
        raise JWTError("Token expired")

    token_type = payload.get("type")
    if expected_type and token_type != expected_type:
        raise JWTError(f"Unexpected token type: {token_type}")
    return payload
