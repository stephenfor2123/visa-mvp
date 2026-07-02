"""Auth endpoint DTOs (request/response) — V2 §4.1.

Account identifier: email or username. Phone-based login removed.
"""
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --------------------------------------------------------------------------- #
# Email / username / account validation                                      #
# --------------------------------------------------------------------------- #
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,31}$")


def _validate_account(v: str) -> str:
    """Account can be either an email or a username."""
    cleaned = (v or "").strip()
    if len(cleaned) < 3 or len(cleaned) > 120:
        raise ValueError("account must be 3-120 characters")
    if _EMAIL_RE.match(cleaned) or _USERNAME_RE.match(cleaned):
        return cleaned
    raise ValueError("account must be a valid email or username")


# --------------------------------------------------------------------------- #
# Requests                                                                   #
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., description="3-32 chars [A-Za-z0-9_.-], must start with letter/digit")
    email: str = Field(..., description="User email (used for login + recovery)")
    password: str = Field(..., min_length=8, max_length=32, description="8-32 chars, letters + digits")
    nickname: Optional[str] = Field(None, max_length=64)
    language_pref: Optional[str] = Field("zh-CN", max_length=8)

    @field_validator("username")
    @classmethod
    def _v_username(cls, v: str) -> str:
        v = (v or "").strip()
        if not _USERNAME_RE.match(v):
            raise ValueError("username must be 3-32 chars [A-Za-z0-9_.-] and start with a letter or digit")
        return v

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email format")
        if len(v) > 120:
            raise ValueError("email must be at most 120 characters")
        return v


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account: str = Field(..., description="Email or username")
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("account")
    @classmethod
    def _v_account(cls, v: str) -> str:
        return _validate_account(v)


class ResetPasswordRequest(BaseModel):
    """Reset by account (email / username) — no SMS code required.

    W26 product change: simplified recovery flow. Admin can also trigger
    a forced reset from the admin panel.
    """
    model_config = ConfigDict(extra="forbid")

    account: str = Field(..., description="Email or username")
    new_password: str = Field(..., min_length=8, max_length=32)

    @field_validator("account")
    @classmethod
    def _v_account(cls, v: str) -> str:
        return _validate_account(v)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class GoogleAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_token: str = Field(..., min_length=1, description="Google ID token from client-side GIS/google_sign_in")


class WechatAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, description="wx.login() one-time code from the miniprogram")


# --------------------------------------------------------------------------- #
# Responses                                                                  #
# --------------------------------------------------------------------------- #
class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    username: Optional[str] = None
    email: Optional[str] = None
    nickname: Optional[str]
    avatar_url: Optional[str]
    language_pref: str
    status: str
    created_at: datetime


class TokenPair(BaseModel):
    """Issued on register / login / refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="Access-token TTL in seconds")
    user: UserPublic
