"""SMS provider DTOs (B-W6-1) — V2 §6.1 standalone SMS service.

Lives separately from `schemas/auth.py` so the standalone
`/api/v2/sms/*` routes (added in W6-1) don't drag in auth-flow
request shapes. Both endpoints can coexist:
  - `/api/v2/auth/send-code` → uses SmsService (DB-backed, in use since W4)
  - `/api/v2/sms/send`      → uses SmsProvider (in-memory, added W6-1)

Locked contract (see pm/wbs/B-W6-1.md):
  - 6-digit OTP, 5 min TTL
  - purpose ∈ {register, login, reset, destroy}
  - mock-only field `code` echoed in /send response (dev-mode)
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


_PHONE_RE = re.compile(r"^\d{6,15}$")
_VALID_PURPOSES = ("register", "login", "reset", "destroy")
_TEMPLATE_PURPOSES = ("register", "login", "reset", "destroy", "generic")


def _normalize_phone(value: str) -> str:
    return value.strip().lstrip("0")


# --------------------------------------------------------------------------- #
# Requests                                                                   #
# --------------------------------------------------------------------------- #
class SendCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(..., description="Phone number without country code")
    phone_country: str = Field("+86", description="E.164 prefix, e.g. '+86'")
    purpose: str = Field("login", description="register / login / reset / destroy")

    @field_validator("phone")
    @classmethod
    def _v_phone(cls, v: str) -> str:
        cleaned = _normalize_phone(v)
        if not _PHONE_RE.match(cleaned):
            raise ValueError("phone must be 6-15 digits")
        return cleaned

    @field_validator("phone_country")
    @classmethod
    def _v_country(cls, v: str) -> str:
        if not v.startswith("+"):
            raise ValueError("phone_country must start with '+', e.g. '+86'")
        digits = v[1:]
        if not digits.isdigit() or not (1 <= len(digits) <= 4):
            raise ValueError("phone_country must be '+' + 1-4 digits")
        return v

    @field_validator("purpose")
    @classmethod
    def _v_purpose(cls, v: str) -> str:
        if v not in _VALID_PURPOSES:
            raise ValueError(f"purpose must be one of {list(_VALID_PURPOSES)}")
        return v


class VerifyCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str
    phone_country: str = "+86"
    code: str = Field(..., description="6-digit SMS code")
    purpose: str = "login"

    @field_validator("phone")
    @classmethod
    def _v_phone(cls, v: str) -> str:
        cleaned = _normalize_phone(v)
        if not _PHONE_RE.match(cleaned):
            raise ValueError("phone must be 6-15 digits")
        return cleaned

    @field_validator("phone_country")
    @classmethod
    def _v_country(cls, v: str) -> str:
        if not v.startswith("+"):
            raise ValueError("phone_country must start with '+'")
        return v

    @field_validator("code")
    @classmethod
    def _v_code(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("code must be exactly 6 digits")
        return v

    @field_validator("purpose")
    @classmethod
    def _v_purpose(cls, v: str) -> str:
        if v not in _VALID_PURPOSES:
            raise ValueError(f"purpose must be one of {list(_VALID_PURPOSES)}")
        return v


class RegisterTemplateRequest(BaseModel):
    """W6-1 stub — actual template registration lands in V2.1 when we wire
    Tencent Cloud. Today we just record the template name + locale in memory
    so frontend dev mode can list known templates."""

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., min_length=2, max_length=64)
    purpose: str = "generic"
    locale: str = Field("zh-CN", description="BCP-47 locale, e.g. zh-CN / en-US")
    body: str = Field(..., min_length=1, max_length=512)

    @field_validator("purpose")
    @classmethod
    def _v_purpose(cls, v: str) -> str:
        if v not in _TEMPLATE_PURPOSES:
            raise ValueError(f"purpose must be one of {list(_TEMPLATE_PURPOSES)}")
        return v


# --------------------------------------------------------------------------- #
# Responses                                                                  #
# --------------------------------------------------------------------------- #
class SendCodeData(BaseModel):
    """Response body for POST /api/v2/sms/send."""

    model_config = ConfigDict(extra="forbid")

    phone: str
    phone_country: str
    purpose: str
    message_id: str
    expires_in: int = Field(..., description="TTL in seconds (always 300 in mock mode)")
    template_id: str = Field(..., description="Resolved template id (mock always returns 'mock_default')")
    # Mock-only echo. Production swap (V2.1 Tencent) will return null.
    code: Optional[str] = Field(None, description="Raw 6-digit code — mock-mode dev echo")


class VerifyCodeData(BaseModel):
    """Response body for POST /api/v2/sms/verify — JWT pair on success."""

    model_config = ConfigDict(extra="forbid")

    verified: bool
    phone: str
    phone_country: str
    purpose: str
    access_token: Optional[str] = Field(None, description="JWT access token (mock: always issued)")
    token_type: str = "Bearer"
    expires_in: Optional[int] = Field(None, description="Access-token TTL in seconds")


class MessageStatusData(BaseModel):
    """Response body for GET /api/v2/sms/{message_id}."""

    model_config = ConfigDict(extra="forbid")

    message_id: str
    status: str = Field(..., description="sent / failed / unknown")
    phone: Optional[str] = None
    phone_country: Optional[str] = None
    purpose: Optional[str] = None
    sent_at: Optional[str] = None


class TemplateData(BaseModel):
    """Response body for POST /api/v2/sms/template."""

    model_config = ConfigDict(extra="forbid")

    template_id: str
    purpose: str
    locale: str
    body: str
    created_at: str