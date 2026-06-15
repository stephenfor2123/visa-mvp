"""Auth endpoint DTOs (request/response) — V2 §4.1."""
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --------------------------------------------------------------------------- #
# Phone validation (intentionally permissive — region-specific in production) #
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

    phone: str = Field(..., description="Phone number without country code")
    phone_country: str = Field("+86", description="E.164 country prefix, e.g. '+86'")
    password: str = Field(..., min_length=8, max_length=32, description="8-32 chars, letters + digits")
    sms_code: str = Field(..., description="6-digit SMS code from /send-code")
    nickname: Optional[str] = Field(None, max_length=64)
    language_pref: Optional[str] = Field("zh-CN", max_length=8)

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


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str
    phone_country: str = "+86"
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("phone")
    @classmethod
    def _v_phone(cls, v: str) -> str:
        return _validate_phone(v)

    @field_validator("phone_country")
    @classmethod
    def _v_country(cls, v: str) -> str:
        return _validate_phone_country(v)


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
    model_config = ConfigDict(extra="forbid")

    phone: str
    phone_country: str = "+86"
    sms_code: str = Field(..., description="6-digit SMS code from /send-code with purpose=reset")
    new_password: str = Field(..., min_length=8, max_length=32)

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
    phone: str
    phone_country: str
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
