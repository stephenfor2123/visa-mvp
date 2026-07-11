"""Material endpoint DTOs (request/response) — V2 §4.3."""
import re
from datetime import datetime
from typing import Any, Optional, Union

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
    # W60: 前端 lightbox 需要原文件 URL + 缩略图 URL 才能预览。
    # 由 api 层在序列化时通过 material_service.build_download_url / build_thumbnail_url 填充。
    download_url: Optional[str] = None
    thumbnail_url: Optional[str] = None


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

    # W22 fix: accept both int (DB id from tests/scripts) and str (frontend "mat_xxx" tokens).
    # Frontend typically sends numeric IDs as strings ("12"), but tests/scripts pass raw int.
    material_ids: list[Union[int, str]] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Material IDs to validate (1-50) — int or str",
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


# --------------------------------------------------------------------------- #
# Preprocess (image auto-scan + crop) — V2 §4.3.3                            #
# --------------------------------------------------------------------------- #
class PreprocessMeta(BaseModel):
    """Diagnostics from the image preprocessing pipeline."""

    width: int
    height: int
    size_bytes: int
    mime_type: str = "image/jpeg"
    confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="0–1, heuristic for how confident we are the detected quad is the document",
    )
    corrected: bool = Field(
        False,
        description="True if perspective correction was applied; False = passthrough",
    )
    corners: Optional[list[list[int]]] = Field(
        None,
        description="Detected 4 corners in original image [TL,TR,BR,BL]; None if no doc found",
    )
    stages: list[str] = Field(
        default_factory=list,
        description="Pipeline stages executed (for telemetry/debug)",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings (e.g. 'image_too_small')",
    )
    blur_score: float = Field(
        0.0,
        description="清晰度: Laplacian variance of the raw capture; higher = sharper",
    )
    is_blurry: bool = Field(
        False,
        description="清晰度: True if blur_score is below the sharpness threshold",
    )
    is_complete: bool = Field(
        True,
        description="完整度: False if the detected document quad touches the frame edge "
        "(physical document likely extends beyond the photo)",
    )


class PreprocessResponse(BaseModel):
    """POST /preprocess response — returns the processed image + diagnostics.

    The image is base64-encoded so it can be returned inline without an
    extra round-trip to a download URL.
    """

    image_base64: str = Field(..., description="Processed image, base64 encoded")
    meta: PreprocessMeta


# --------------------------------------------------------------------------- #
# Classify (auto material type) — V2 §4.3.4                                   #
# --------------------------------------------------------------------------- #
class ClassifyHint(BaseModel):
    """Single keyword/regex hit that contributed to the classification."""

    source: str = Field(..., description="filename | ocr_field | ocr_text | mime")
    match: str = Field(..., description="what matched (e.g. 'passport_no', 'passport.jpg')")
    weight: float = Field(..., description="how much this match contributed to the score")


class ClassifyResult(BaseModel):
    """One candidate material type with score."""

    material_type: str
    score: float = Field(..., ge=0.0, description="Higher = more likely")
    reasons: list[str] = Field(default_factory=list)


class ClassifyResponse(BaseModel):
    """POST /classify response."""

    predicted_type: str = Field(..., description="Top-1 candidate material type")
    confidence: float = Field(..., ge=0.0, le=1.0)
    candidates: list[ClassifyResult] = Field(
        default_factory=list,
        description="Top-3 candidates ordered by score",
    )
    hints: list[ClassifyHint] = Field(
        default_factory=list,
        description="All keyword/regex hits that contributed (for transparency)",
    )


class ConfirmClassificationRequest(BaseModel):
    """POST /{id}/classification — user confirms or corrects the AI guess."""

    model_config = ConfigDict(extra="forbid")

    material_type: str
    confirmed: bool = Field(
        True,
        description=(
            "True if user accepts the AI guess; False if they correct it. "
            "We use this to learn (store classification_corrected only when wrong)."
        ),
    )


# --------------------------------------------------------------------------- #
# Diagnose (AI refusal-risk assessment) — V2 §4.3.5                           #
# --------------------------------------------------------------------------- #
class ProcessMaterialResponse(BaseModel):
    """POST /process — ephemeral OCR result (file bytes are not stored)."""

    material_type: str
    fields: dict[str, Any] = Field(default_factory=dict)
    is_blurry: bool = False
    is_complete: bool = True
    ocr_status: str = "done"
    pages_processed: int = 0
    bank_analysis: Optional[dict[str, Any]] = None


class MaterialSnapshotIn(BaseModel):
    """Client-side material summary for /diagnose (no stored files)."""

    item_key: str = Field(..., min_length=1, max_length=64)
    material_type: str
    ocr_result: dict[str, Any] = Field(default_factory=dict)


class DiagnoseIssue(BaseModel):
    """One potential issue / improvement opportunity in the application."""

    code: str = Field(..., description="stable identifier, e.g. 'passport.expiry_short'")
    severity: str = Field(..., description="info | warning | error | critical")
    title: str
    detail: str
    fix_suggestion: Optional[str] = None
    related_material_id: Optional[int] = None
    related_item_key: Optional[str] = Field(
        None, description="Wizard item key when materials are browser-local only"
    )
    # W46: i18n keys + structured params. When set, frontend should look these
    # up in its own locale and interpolate `params` instead of rendering the
    # pre-rendered zh-CN `title`/`detail` strings.
    title_key: Optional[str] = None
    detail_key: Optional[str] = None
    fix_key: Optional[str] = None
    params: Optional[dict] = Field(
        default=None,
        description="raw values behind the pre-rendered zh-CN title/detail (e.g. {'months': 6, 'expiry': '2030-12-31'}), so frontends can re-render the message in the user's own locale instead of showing the server's zh-CN text",
    )


class DiagnoseRequest(BaseModel):
    """POST /diagnose request — diagnose the refusal risk of an application."""

    model_config = ConfigDict(extra="forbid")

    material_ids: list[int] = Field(
        default_factory=list,
        max_length=50,
        description="Legacy: stored material IDs (deprecated — use materials_snapshot)",
    )
    materials_snapshot: list[MaterialSnapshotIn] = Field(
        default_factory=list,
        max_length=50,
        description="Ephemeral OCR summaries from the browser (preferred)",
    )
    country_code: str = Field(
        ...,
        min_length=2,
        max_length=8,
        description="Destination country code, e.g. 'US', 'VN', 'ID'",
    )
    visa_type: Optional[str] = Field(
        None,
        description="Visa subclass, e.g. 'B1', 'tourist', 'student'. Optional.",
    )
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional form fields (travel_date, purpose, etc.)",
    )


class DiagnoseResponse(BaseModel):
    """POST /diagnose response — overall risk + per-issue breakdown."""

    overall_risk: str = Field(
        ..., description="low | medium | high | critical"
    )
    risk_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="0 = no risk, 1 = certain refusal",
    )
    summary: str
    issues: list[DiagnoseIssue]
    positives: list[str] = Field(
        default_factory=list,
        description="Things that look good (so user doesn't only see negatives)",
    )
    policy_refs: list[str] = Field(
        default_factory=list,
        description="RAG-sourced policy URLs/snippets that informed the diagnosis",
    )
    rule_count: int = Field(..., description="How many rules were evaluated")
