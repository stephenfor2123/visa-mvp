"""Magic-byte validation for uploaded visa materials.

Rejects spoofed content-types (e.g. executable bytes declared as image/png).
Allowed types align with validation_rules.json IMAGE_FORMAT_ALLOWED.
"""
from __future__ import annotations

from typing import Optional

from app.core.errors import BizException, ErrorCode

_ALLOWED_MIMES = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
})

_MIME_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
}


def detect_mime_from_bytes(data: bytes) -> Optional[str]:
    """Return MIME type guessed from file header, or None if unrecognized."""
    if not data:
        return None

    head = data[:16]
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF"):
        return "application/pdf"
    return None


def _normalize_declared_mime(mime_type: str) -> str:
    raw = (mime_type or "").lower().split(";")[0].strip()
    return _MIME_ALIASES.get(raw, raw)


def validate_upload_bytes(data: bytes, declared_mime: str = "") -> str:
    """Validate upload content and return the trusted MIME type.

    Raises BizException(INVALID_FORMAT) when magic bytes are missing,
    the type is not allowed, or declared content-type does not match content.
    """
    detected = detect_mime_from_bytes(data)
    if detected is None:
        raise BizException(
            ErrorCode.INVALID_FORMAT,
            message="Unrecognized file format (magic bytes mismatch)",
        )
    if detected not in _ALLOWED_MIMES:
        raise BizException(
            ErrorCode.INVALID_FORMAT,
            message=f"File type {detected} is not allowed",
        )

    declared = _normalize_declared_mime(declared_mime)
    if declared and declared != detected:
        raise BizException(
            ErrorCode.INVALID_FORMAT,
            message="Declared content-type does not match file contents",
        )
    return detected
