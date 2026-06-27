"""Auth endpoint DTOs (request/response) — V2 §4.1.

W26 product change: identifier is now email / username, not phone.
Phone-based schemas (SmsLoginRequest, SendCodeRequest) are kept for the
sms-login endpoint that admin tools still use, but the main user-facing
register / login / reset-password all use account (email or username).
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
# Phone validation (legacy — kept for sms-login endpoint)                    #
# --------------------------------------------------------------------------- #
_PHONE_RE = re.compile(r"^\d{6,15}$")


def _normalize_phone(value: str) -> str:
    return value.strip().lstrip("0")


def _validate_phone(v: str) -> str:
    cleaned = _normalize_phone(v)
    if not _PHONE_RE.match(cleaned):
        raise ValueError("phone must be 6-15 digits")
    return cleaned


def _validate_phone_country(v: str) -> str:
    if not v.startswith("+"):
        raise ValueError("phone_country must start with '+', e.g. '+86'")
    digits = v[1:]
    if not digits.isdigit() or not (1 <= len(digits) <= 4):
        raise ValueError("phone_country must be '+' + 1-4 digits")
    return v


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


# --------------------------------------------------------------------------- #
# Legacy phone-based DTOs (kept for sms-login / send-code / reset-password) #
# --------------------------------------------------------------------------- #
class SmsLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str
    phone_country: str = "+86"
    sms_code: str

    @field_validator("phone")
    @classmethod
    def _v_phone(cls, v: str) -> str:
        return _validate_phone(v)

    @field_validator("phone_country")
    @classmethod
    def _v_country(cls, v: str) -> str:
        return _validate_phone_country(v)

    @field_validator("sms_code")
    @classmethod
    def _v_sms_code(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("sms_code must be exactly 6 digits")
        return v


class SendCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str
    phone_country: str = "+86"
    purpose: str = Field("login", description="register / login / reset / destroy")

    @field_validator("phone")
    @classmethod
    def _v_phone(cls, v: str) -> str:
        return _validate_phone(v)

    @field_validator("phone_country")
    @classmethod
    def _v_country(cls, v: str) -> str:
        return _validate_phone_country(v)

    @field_validator("purpose")
    @classmethod
    def _v_purpose(cls, v: str) -> str:
        allowed = {"register", "login", "reset", "destroy"}
        if v not in allowed:
            raise ValueError(f"purpose must be one of {sorted(allowed)}")
        return v


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


# --------------------------------------------------------------------------- #
# Responses                                                                  #
# --------------------------------------------------------------------------- #
class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    phone_country: Optional[str] = None
    nickname: Optional[str]
    avatar_url: Optional[str]
    language_pref: str
    status: str
    created_at: datetime


class TokenPair(BaseModel):
    """Issued on register / login / sms-login / refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="Access-token TTL in seconds")
    user: UserPublic
