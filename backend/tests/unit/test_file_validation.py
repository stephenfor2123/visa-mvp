"""Unit tests for file magic-byte validation."""
from __future__ import annotations

import pytest

from app.core.errors import BizException, ErrorCode
from app.core.file_validation import detect_mime_from_bytes, validate_upload_bytes

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"x" * 32
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"x" * 32
PDF_BYTES = b"%PDF-1.4\n" + b"x" * 32
WEBP_BYTES = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"x" * 8
EVIL_BYTES = b"MZtest\n"


class TestDetectMime:
    def test_jpeg(self):
        assert detect_mime_from_bytes(JPEG_BYTES) == "image/jpeg"

    def test_png(self):
        assert detect_mime_from_bytes(PNG_BYTES) == "image/png"

    def test_pdf(self):
        assert detect_mime_from_bytes(PDF_BYTES) == "application/pdf"

    def test_webp(self):
        assert detect_mime_from_bytes(WEBP_BYTES) == "image/webp"

    def test_unknown(self):
        assert detect_mime_from_bytes(EVIL_BYTES) is None


class TestValidateUploadBytes:
    def test_matching_declared_mime_ok(self):
        assert validate_upload_bytes(PNG_BYTES, "image/png") == "image/png"

    def test_no_declared_mime_uses_detected(self):
        assert validate_upload_bytes(JPEG_BYTES, "") == "image/jpeg"

    def test_mismatch_rejected(self):
        with pytest.raises(BizException) as exc:
            validate_upload_bytes(JPEG_BYTES, "image/png")
        assert exc.value.code == ErrorCode.INVALID_FORMAT

    def test_unknown_bytes_rejected(self):
        with pytest.raises(BizException) as exc:
            validate_upload_bytes(EVIL_BYTES, "image/png")
        assert exc.value.code == ErrorCode.INVALID_FORMAT
