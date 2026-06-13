"""
Security helpers: password hashing (bcrypt cost=12), JWT encode/decode,
current-user dependency.

Per V2 §4.1.4:
  - bcrypt cost 12, password 8-32 chars, must contain letters + digits
  - Access token TTL 2h, Refresh token 7d sliding
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.errors import BizException, ErrorCode
from app.models.user import User


# ------------------------------------------------------------------ #
# Password                                                            #
# ------------------------------------------------------------------ #
# passlib CryptContext; bcrypt cost from settings.
_pwd_context: CryptContext | None = None


def _pwd_ctx(settings: Settings) -> CryptContext:
    global _pwd_context
    if _pwd_context is None:
        _pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=settings.bcrypt_cost,
        )
    return _pwd_context


def hash_password(plain: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return _pwd_ctx(settings).hash(plain)


def verify_password(plain: str, hashed: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    try:
        return _pwd_ctx(settings).verify(plain, hashed)
    except Exception:
        return False


# Stronger rule than just length: must have at least one letter and one digit.
_PASSWORD_STRONG_RE = re.compile(r"[A-Za-z]")  # any ASCII letter
_PASSWORD_DIGIT_RE = re.compile(r"\d")


def validate_password_strength(plain: str, settings: Settings | None = None) -> None:
    """Raise BizException(PASSWORD_TOO_WEAK) on weak password.

    Rule: length 8-32 AND contains at least one letter AND at least one digit.
    """
    settings = settings or get_settings()
    if not (settings.password_min_length <= len(plain) <= settings.password_max_length):
        raise BizException(
            ErrorCode.PASSWORD_TOO_WEAK,
            message=(
                f"Password length must be {settings.password_min_length}-"
                f"{settings.password_max_length} characters"
            ),
        )
    if not _PASSWORD_STRONG_RE.search(plain) or not _PASSWORD_DIGIT_RE.search(plain):
        raise BizException(
            ErrorCode.PASSWORD_TOO_WEAK,
            message="Password must contain both letters and digits",
        )


# ------------------------------------------------------------------ #
# JWT                                                                 #
# ------------------------------------------------------------------ #
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

_bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    user_id: int,
    settings: Settings | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    settings = settings or get_settings()
    now = _now_utc()
    exp = now + timedelta(minutes=settings.access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(8),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, exp


def create_refresh_token(
    user_id: int,
    settings: Settings | None = None,
) -> tuple[str, datetime]:
    settings = settings or get_settings()
    now = _now_utc()
    exp = now + timedelta(days=settings.refresh_token_ttl_days)
    payload = {
        "sub": str(user_id),
        "type": TOKEN_TYPE_REFRESH,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(16),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, exp


def decode_token(token: str, expected_type: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        # Token signature invalid / malformed / wrong algo
        if expected_type == TOKEN_TYPE_REFRESH:
            raise BizException(
                ErrorCode.REFRESH_TOKEN_INVALID, message="Invalid refresh token"
            ) from None
        raise BizException(
            ErrorCode.UNAUTHORIZED, message="Invalid token"
        ) from None

    if payload.get("type") != expected_type:
        if expected_type == TOKEN_TYPE_REFRESH:
            raise BizException(
                ErrorCode.REFRESH_TOKEN_INVALID, message="Wrong token type"
            )
        raise BizException(ErrorCode.UNAUTHORIZED, message="Wrong token type")

    exp = payload.get("exp")
    if exp is not None and datetime.fromtimestamp(int(exp), tz=timezone.utc) < _now_utc():
        if expected_type == TOKEN_TYPE_REFRESH:
            raise BizException(
                ErrorCode.REFRESH_TOKEN_EXPIRED, message="Refresh token expired"
            )
        raise BizException(ErrorCode.UNAUTHORIZED, message="Token expired")

    return payload


# ------------------------------------------------------------------ #
# Current user dependency                                            #
# ------------------------------------------------------------------ #
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve access token from Authorization: Bearer ... -> User row."""
    if credentials is None or not credentials.credentials:
        raise BizException(ErrorCode.UNAUTHORIZED, message="Missing bearer token")

    payload = decode_token(credentials.credentials, TOKEN_TYPE_ACCESS)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise BizException(ErrorCode.UNAUTHORIZED, message="Bad token subject") from None

    user = await db.get(User, user_id)
    if user is None:
        raise BizException(ErrorCode.USER_NOT_FOUND, message="User not found")

    if user.status != "active":
        raise BizException(ErrorCode.ACCOUNT_DISABLED, message="Account is not active")

    return user
