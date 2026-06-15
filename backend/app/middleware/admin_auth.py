"""
Admin authentication middleware — bearer JWT with role=admin.

Independent from the C-user JWT (different secret + claims structure).
All /admin/* endpoints are protected by verify_admin_token.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.errors import BizException, ErrorCode
from app.schemas.admin import AdminTokenData


_admin_bearer = HTTPBearer(auto_error=False, description="Admin JWT access token")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_admin_token(
    admin_id: int,
    username: str,
    settings: Optional[Any] = None,
) -> tuple[str, datetime]:
    """Create an admin JWT with role=admin."""
    import secrets

    settings = settings or get_settings()
    now = _now_utc()
    exp = now + timedelta(minutes=settings.access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(admin_id),
        "type": "admin_access",
        "role": "admin",
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(8),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, exp


def decode_admin_token(token: str, settings: Optional[Any] = None) -> dict[str, Any]:
    """Decode and validate an admin token. Raises BizException on failure."""
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise BizException(ErrorCode.UNAUTHORIZED, message="Invalid admin token")

    if payload.get("role") != "admin":
        raise BizException(ErrorCode.FORBIDDEN, message="Not an admin token")

    exp = payload.get("exp")
    if exp is not None and datetime.fromtimestamp(int(exp), tz=timezone.utc) < _now_utc():
        raise BizException(ErrorCode.UNAUTHORIZED, message="Admin token expired")

    return payload


async def verify_admin_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_admin_bearer),
) -> AdminTokenData:
    """FastAPI dependency — resolve admin bearer token to AdminTokenData."""
    if credentials is None or not credentials.credentials:
        raise BizException(
            ErrorCode.UNAUTHORIZED, message="Missing admin bearer token"
        )

    payload = decode_admin_token(credentials.credentials)
    try:
        admin_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise BizException(ErrorCode.UNAUTHORIZED, message="Bad admin token subject")

    return AdminTokenData(
        admin_id=admin_id,
        username=payload.get("username", "admin"),
        role=payload.get("role", "admin"),
    )
