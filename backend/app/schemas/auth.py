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
    email_code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code from email")
    nickname: Optional[str] = Field(None, max_length=64)
    language_pref: Optional[str] = Field("zh-CN", max_length=8)
    age_confirmed_16: bool = Field(
        ...,
        description="GDPR Art.8 — user must confirm they are 16 or older",
    )

    @field_validator("age_confirmed_16")
    @classmethod
    def _v_age(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("You must confirm you are at least 16 years old")
        return v

    @field_validator("email_code")
    @classmethod
    def _v_email_code(cls, v: str) -> str:
        v = (v or "").strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("email_code must be exactly 6 digits")
        return v

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


class SendEmailCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., description="Target email for the verification code")
    purpose: str = Field("register", description="register")
    language_pref: Optional[str] = Field("en", max_length=8, description="en | zh-CN | vi | id")

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email format")
        return v

    @field_validator("purpose")
    @classmethod
    def _v_purpose(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in {"register"}:
            raise ValueError("purpose must be 'register'")
        return v


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account: str = Field(..., description="Email or username")
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("account")
    @classmethod
    def _v_account(cls, v: str) -> str:
        return _validate_account(v)


class PasswordResetRequest(BaseModel):
    """Step 1: request a password-reset link sent to the account's registered email."""
    model_config = ConfigDict(extra="forbid")

    account: str = Field(..., description="Email or username used at signup")

    @field_validator("account")
    @classmethod
    def _v_account(cls, v: str) -> str:
        return _validate_account(v)


class ResetPasswordRequest(BaseModel):
    """Step 2: set a new password using the token from the reset email."""
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., min_length=10, description="JWT from password-reset email link")
    new_password: str = Field(..., min_length=8, max_length=32)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class GoogleAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_token: str = Field(..., min_length=1, description="Google ID token from client-side GIS/google_sign_in")
    age_confirmed_16: bool = Field(
        False,
        description="Required when auto-registering a new Google user (Art.8)",
    )


class WechatAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, description="wx.login() one-time code from the miniprogram")
    age_confirmed_16: bool = Field(
        False,
        description="Required when auto-registering a new WeChat user (Art.8)",
    )

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
