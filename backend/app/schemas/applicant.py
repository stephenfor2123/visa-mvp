"""Applicant profile CRUD schemas — W1 personal applicant library.

A user may have multiple applicants. Each applicant has a
(surname, given_name) and a passport_no. Field shape intentionally
matches the existing order.applicant_data so that future V2.1 can
hydrate the order form from a chosen applicant without remapping.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# Passport number rules (W1 — basic only).
# W1: 5-32 chars, letters/digits/spaces/dashes allowed. No country-specific
# pattern; that lands in W2 with the OCR integration.
_PASSPORT_RE = re.compile(r"^[A-Za-z0-9 \-]{5,32}$")
# Names: 1-64 chars; allow CJK + Latin + spaces + hyphens + apostrophes.
_NAME_RE = re.compile(r"^[\w '\-一-鿿]{1,64}$", re.UNICODE)


class ApplicantCreate(BaseModel):
    surname: str = Field(..., min_length=1, max_length=64, description="Family name (as on passport)")
    given_name: str = Field(..., min_length=1, max_length=64, description="Given name (as on passport)")
    passport_no: str = Field(..., min_length=5, max_length=32, description="Passport number")

    @field_validator("surname", "given_name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if not _NAME_RE.match(v):
            raise ValueError("Name contains invalid characters")
        return v

    @field_validator("passport_no")
    @classmethod
    def _validate_passport(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Passport number cannot be empty")
        if not _PASSPORT_RE.match(v):
            raise ValueError("Passport number must be 5-32 characters of letters/digits/spaces/dashes")
        # Store uppercase to avoid case-only dupes.
        return v.upper().replace(" ", "")


class ApplicantUpdate(BaseModel):
    surname: Optional[str] = Field(None, min_length=1, max_length=64)
    given_name: Optional[str] = Field(None, min_length=1, max_length=64)
    passport_no: Optional[str] = Field(None, min_length=5, max_length=32)

    @field_validator("surname", "given_name")
    @classmethod
    def _validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if not _NAME_RE.match(v):
            raise ValueError("Name contains invalid characters")
        return v

    @field_validator("passport_no")
    @classmethod
    def _validate_passport(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Passport number cannot be empty")
        if not _PASSPORT_RE.match(v):
            raise ValueError("Passport number must be 5-32 characters of letters/digits/spaces/dashes")
        return v.upper().replace(" ", "")


class ApplicantItem(BaseModel):
    id: int
    surname: str
    given_name: str
    display_name: str = Field(..., description="surname + given_name, smart-joined")
    passport_no: str
    created_at: datetime
    updated_at: datetime


class ApplicantListResponse(BaseModel):
    items: list[ApplicantItem]
    total: int = Field(..., description="Total count for the current user (W1 cap: 10)")


class ApplicantCreateResponse(BaseModel):
    applicant: ApplicantItem
