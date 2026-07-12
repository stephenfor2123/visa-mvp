"""Order endpoint DTOs (request/response) — V2 §4.2."""
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.order import VISA_TYPES


# --------------------------------------------------------------------------- #
# Request                                                                     #
# --------------------------------------------------------------------------- #
class CreateOrderRequest(BaseModel):
    """POST /api/v2/orders body — V2 §4.2.3."""

    model_config = ConfigDict(extra="forbid")

    destination_id: int = Field(..., ge=1, description="Target country/destination id")
    visa_type: str = Field(..., description="tourism | student")
    material_ids: list[int] = Field(
        default_factory=list,
        max_length=50,
        description="Deprecated — files are not stored; keep empty for privacy-first flow",
    )
    applicant_data: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Structured applicant form fields "
            "(name, gender, dob, nationality, passport_no, etc.)"
        ),
    )
    aff_code: Optional[str] = Field(
        default=None,
        max_length=32,
        description=(
            "Optional affiliate partner code (B-W9-3, V2 §4.7). When set, "
            "the order is auto-attributed to the matching partner on creation. "
            "Case-insensitive; whitespace stripped server-side."
        ),
    )

    @field_validator("visa_type")
    @classmethod
    def _check_visa_type(cls, v: str) -> str:
        if v not in VISA_TYPES:
            raise ValueError(f"visa_type must be one of {sorted(VISA_TYPES)}")
        return v


# --------------------------------------------------------------------------- #
# Response                                                                    #
# --------------------------------------------------------------------------- #
class OrderMaterialRef(BaseModel):
    """Lightweight material reference embedded in order detail.

    The full material detail endpoint is `/api/v2/materials/{id}`; we embed
    just the essentials so the order-detail view doesn't need N extra round
    trips on the happy path.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    material_type: str
    original_filename: str
    mime_type: str
    file_size: int
    ocr_status: str


class OrderStatusHistoryItem(BaseModel):
    """One row in the state-transition log."""

    model_config = ConfigDict(from_attributes=True)

    from_status: Optional[str]
    to_status: str
    source: str
    note: Optional[str]
    created_at: datetime


class OrderMessageItem(BaseModel):
    """One notification message attached to the order."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    channel: str
    title: str
    body: str
    sent_at: Optional[datetime]
    read_at: Optional[datetime]
    created_at: datetime


class OrderOut(BaseModel):
    """Public order representation — list & create response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    order_no: str
    user_id: int
    destination_id: int
    # W2: country_code/country_name surfaced so the order list can render
    # a flag + country name without a second roundtrip to /destinations.
    # Falls back gracefully if destination row is missing (deleted etc).
    country_code: str = Field(default="", description="ISO 2-letter country code, '' if unavailable")
    country_name: str = Field(default="", description="Country display name (i18n-aware)")
    visa_type: str
    status: str
    total_amount: Decimal
    currency: str
    rpa_task_id: Optional[str]
    destination_url: Optional[str]
    aff_code: Optional[str] = None
    material_ids: list[int] = Field(default_factory=list)
    applicant_data: dict[str, Any] = Field(default_factory=dict)
    submitted_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    closed_at: Optional[datetime]
    ds160_portal_submitted_at: Optional[datetime] = Field(
        default=None,
        description="US: DS-160 portal submit milestone (alias of portal_submitted_at)",
    )
    locked_until: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    diagnosis_completed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    portal_submitted_at: Optional[datetime] = None
    portal_submitted_source: Optional[str] = None
    refund_status: str = "none"
    refund_reason: Optional[str] = None
    refund_amount: Optional[Decimal] = None
    refund_requested_at: Optional[datetime] = None
    refund_approved_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class OrderDetailOut(OrderOut):
    """Order + status history + messages (returned by GET /{order_no})."""

    status_history: list[OrderStatusHistoryItem] = Field(default_factory=list)
    messages: list[OrderMessageItem] = Field(default_factory=list)
    materials: list[OrderMaterialRef] = Field(default_factory=list)


class OrderListResponse(BaseModel):
    """GET /api/v2/orders response with pagination metadata."""

    items: list[OrderOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class CreateOrderResponse(BaseModel):
    """POST /api/v2/orders response."""

    order: OrderOut
    order_no: str
    status: str


class CancelOrderResponse(BaseModel):
    """POST /api/v2/orders/{order_no}/cancel response."""

    order_no: str
    status: str
    cancelled_at: datetime


class DeleteDraftResponse(BaseModel):
    """DELETE /api/v2/orders/{order_no} response — W67.

    Returns the deleted order's order_no, plus the count of materials that
    were soft-deleted as part of the cascade. Front-end uses the count to
    surface a "X materials cleared" hint in the success toast.
    """

    order_no: str
    deleted: bool = Field(..., description="True when the order row was physically removed")
    soft_deleted_materials: int = Field(
        ..., ge=0,
        description="Number of material rows whose deleted_at was stamped "
                    "(draft-only; included materials are hidden from the "
                    "user's library but the rows stay for audit/recovery).",
    )
    deleted_at: datetime


class SubmitOrderRequest(BaseModel):
    """POST /api/v2/orders/{order_no}/submit body — V2 §4.2.4.

    The client must echo the `signature` it received from
    `GET /api/v2/orders/{order_no}/checklist`. The server re-derives the
    signature from the locked snapshot and rejects the request with 4011
    if they don't match (the data changed under the user's feet, or the
    client fabricated a signature without first viewing the checklist).
    """

    model_config = ConfigDict(extra="forbid")

    signature: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hex of the locked checklist snapshot (from GET /checklist)",
    )

    @field_validator("signature")
    @classmethod
    def _check_signature_hex(cls, v: str) -> str:
        if not re.fullmatch(r"[a-f0-9]{64}", v):
            raise ValueError("signature must be 64-char lowercase hex (SHA-256)")
        return v


class SubmitOrderResponse(BaseModel):
    """POST /api/v2/orders/{order_no}/submit response."""

    order_no: str
    status: str
    submitted_at: datetime
    rpa_task_id: str


class DiagnosisCompleteResponse(BaseModel):
    order_no: str
    status: str
    diagnosis_completed_at: datetime
    completed_at: datetime


class PortalSubmittedResponse(BaseModel):
    order_no: str
    portal_submitted_at: datetime
    portal_submitted_source: str
    unchanged: bool = False


class RefundRequestBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)
    amount: Optional[Decimal] = Field(default=None, ge=0)


class RefundRequestResponse(BaseModel):
    order_no: str
    refund_status: str
    refund_requested_at: datetime


class OrderAttentionCounts(BaseModel):
    payment_expiring_soon: int = 0
    paid_awaiting_diagnosis: int = 0
    completed_awaiting_portal: int = 0
    refund_pending: int = 0
    refund_failed: int = 0
