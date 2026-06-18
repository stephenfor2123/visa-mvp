"""Material endpoint DTOs (request/response) — V2 §4.3."""
import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.material import MATERIAL_TYPES


# --------------------------------------------------------------------------- #
# Common                                                                     #
# --------------------------------------------------------------------------- #
class MaterialOut(BaseModel):
    """Public material metadata (returned by /upload, /{id}, list)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    user_id: int
    order_id: Optional[int]
    material_type: str
    original_filename: str
    mime_type: str
    file_size: int
    sha256: str
    storage_key: str
    thumbnail_key: Optional[str]
    encryption_key_id: str
    ocr_status: str
    classification: Optional[str]
    classification_corrected: Optional[str]
    expires_at: Optional[datetime]
    archived: bool
    created_at: datetime


class MaterialDetailOut(MaterialOut):
    """Same as MaterialOut but includes the parsed ocr_result JSON."""

    ocr_result: Optional[dict[str, Any]] = None


class UploadResponse(BaseModel):
    """POST /upload response — 201 created."""

    material: MaterialOut
    deduplicated: bool = Field(
        False, description="True when an existing row was returned instead of a new one"
    )
    download_url: str = Field(..., description="5-min signed URL to fetch the file")
    thumbnail_url: Optional[str] = None


class DownloadResponse(BaseModel):
    url: str
    expires_in: int
    filename: str


# --------------------------------------------------------------------------- #
# Validation                                                                 #
# --------------------------------------------------------------------------- #
class ValidateRequest(BaseModel):
    """POST /validate request — runs all enabled rules against given materials."""

    model_config = ConfigDict(extra="forbid")

    # W19: accept string IDs (frontend uses "mat_xxx" prefixed IDs, not numeric)
    material_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Material IDs to validate (1-50)",
    )
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional extracted form fields to validate alongside OCR "
            "(e.g. {'passport_no': 'G12345678', 'expiry': '2030-01-01'})"
        ),
    )


class ValidationIssue(BaseModel):
    code: str
    severity: str  # pass | warning | error
    message_key: str
    material_id: Optional[int] = None
    details: dict[str, Any] = Field(default_factory=dict)


class ValidateResponse(BaseModel):
    overall: str = Field(..., description="pass | warning | error")
    issues: list[ValidationIssue]
    rule_count: int
    materials_checked: int
    fields_checked: dict[str, Any]


# --------------------------------------------------------------------------- #
# Helpers / shared validators                                                 #
# --------------------------------------------------------------------------- #
def _validate_material_type(v: str) -> str:
    if v not in MATERIAL_TYPES:
        raise ValueError(
            f"material_type must be one of {sorted(MATERIAL_TYPES)}"
        )
    return v


# File-name sanitization used for storage keys. Strips path separators and
# any non-safe characters. Falls back to 'file' if nothing safe is left.
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str, fallback: str = "file") -> str:
    name = (name or "").strip().replace("\\", "/").split("/")[-1]
    name = _SAFE_NAME_RE.sub("_", name)
    if not name or name in {".", ".."}:
        return fallback
    return name[:200]
