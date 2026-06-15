"""Checklist DTOs (V2 §4.2.3) — pre-submit confirmation view.

Returned by `GET /api/v2/orders/{order_no}/checklist`.

The checklist view is a **read-only, locked snapshot** of everything the user
is about to commit to the visa application:
  - order identity + state (must be `created` to be visible)
  - destination + visa_type
  - applicant form fields (7 fields, read-only)
  - travel window (arrival / departure / stay days)
  - emergency contact (3 fields, read-only)
  - material list (id / type / filename / ocr status)
  - a deterministic `signature` (SHA-256 of the snapshot) so the front-end
    can prove the user saw this exact data at submit time.

No new error codes are introduced here — we reuse 4xxx for ownership/status
errors (see `app/core/errors.py`).
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Sub-DTOs (all read-only, no validators — these are display values)          #
# --------------------------------------------------------------------------- #
class ApplicantSnapshot(BaseModel):
    """The 7 applicant fields captured during form fill (V2 §4.1.4 / §4.2.3).

    All fields are optional in the response because the user might still be
    editing on the form page when this endpoint is hit. Empty strings mean
    "user has not filled this in yet".
    """

    model_config = ConfigDict(from_attributes=True)

    surname: str = Field(default="", description="Family name (uppercase)")
    given_name: str = Field(default="", description="Given name (uppercase)")
    sex: str = Field(default="", description="M / F / X")
    dob: str = Field(default="", description="ISO 8601 date string YYYY-MM-DD")
    nationality: str = Field(default="", description="ISO 3166-1 alpha-2 (e.g. CN)")
    passport_no: str = Field(default="", description="Passport number (uppercase)")
    passport_expiry: str = Field(
        default="", description="ISO 8601 date string YYYY-MM-DD"
    )


class EmergencyContactSnapshot(BaseModel):
    """The 3 emergency-contact fields (V2 §4.1.4 emergency_contact)."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(default="", description="Contact full name")
    phone: str = Field(default="", description="E.164 or local phone")
    relation: str = Field(
        default="", description="Relationship (parent / spouse / sibling / friend / other)"
    )


class DestinationSnapshot(BaseModel):
    """Resolved destination details (joined from visa_destinations)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    country_code: str
    country_name: str = Field(
        default="",
        description="Display name in the user's language (zh-CN / en fallback)",
    )
    enabled: bool


class MaterialChecklistItem(BaseModel):
    """One material in the checklist (lightweight view)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    material_type: str
    original_filename: str
    mime_type: str
    file_size: int
    ocr_status: str
    expires_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# Top-level response                                                          #
# --------------------------------------------------------------------------- #
class ChecklistOut(BaseModel):
    """GET /api/v2/orders/{order_no}/checklist response.

    `signature` is a deterministic hash of the locked snapshot so the front-end
    can pass it back to a future `POST /submit` (W2-D4) to prove the user
    saw this exact view. Recomputed on every request — no DB persistence.
    """

    model_config = ConfigDict(from_attributes=True)

    order_no: str
    status: str
    visa_type: str

    destination: DestinationSnapshot
    applicant: ApplicantSnapshot
    travel_window: dict = Field(
        default_factory=dict,
        description="arrival_date / departure_date / stay_days (all optional strings)",
    )
    emergency_contact: EmergencyContactSnapshot
    materials: list[MaterialChecklistItem] = Field(default_factory=list)

    # Locked-signature: SHA-256 hex of (applicant + travel + emergency + materials)
    signature: str = Field(
        ..., description="SHA-256 hex of the snapshot payload (locked read-only view)"
    )
    generated_at: datetime = Field(
        ..., description="Server-side timestamp the snapshot was built"
    )


class ChecklistResponse(BaseModel):
    """ApiResponse envelope wrapper — V2 §1.5.1.

    Use `ApiResponse[ChecklistOut]` directly in the route; this class is
    exposed for tests that want a typed body.
    """

    code: str = "1000"
    message: str = "OK"
    data: ChecklistOut
