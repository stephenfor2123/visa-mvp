"""OCR integration tests — V2 §5.1."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.ocr import OCREngine

# --------------------------------------------------------------------------- #
# Fixtures                                                                  #
# --------------------------------------------------------------------------- #
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


# --------------------------------------------------------------------------- #
# Test OCR Engine (unit-level, no DB needed)                                 #
# --------------------------------------------------------------------------- #
class TestOCREngine:
    @pytest.mark.asyncio
    async def test_ocr_engine_basic(self):
        """
        OCREngine('en') can recognize a sample image.
        Verifies: engine init + recognize returns a list (empty or with items).
        """
        from PIL import Image

        img_path = FIXTURE_DIR / "sample_passport.jpg"
        assert img_path.exists(), f"fixture not found: {img_path}"

        # Load fixture image as PIL, convert to numpy BGR for PaddleOCR
        img_pil = Image.open(img_path).convert("RGB")
        import numpy as np

        img_array = np.array(img_pil)
        import cv2

        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # OCREngine init (lang='en')
        engine = OCREngine(lang="en")
        assert engine.lang == "en"

        # recognize() returns a list (may be empty or with text items)
        items = engine.recognize(img_bgr)
        assert isinstance(items, list), "recognize must return a list"
        # Basic sanity: no crash, structure is correct
        for item in items:
            assert "text" in item
            assert "bbox" in item
            assert "confidence" in item
            assert isinstance(item["text"], str)
            assert isinstance(item["bbox"], list)
            assert isinstance(item["confidence"], float)

    @pytest.mark.asyncio
    async def test_ocr_engine_all_supported_langs(self):
        """OCREngine can be instantiated with all supported lang keys."""
        from app.services.ocr import SUPPORTED_LANGS

        for lang in SUPPORTED_LANGS:
            engine = OCREngine(lang=lang)
            assert engine.lang is not None


# --------------------------------------------------------------------------- #
# Test OCR endpoint auth                                                   #
# --------------------------------------------------------------------------- #
class TestOCREndpointAuth:
    @pytest.mark.asyncio
    async def test_ocr_endpoint_auth_required(self, client: AsyncClient):
        """
        POST /api/v2/ocr/recognize without token → 401 UNAUTHORIZED.
        Follows the same auth pattern as destinations.py.
        """
        fixture_path = FIXTURE_DIR / "sample_passport.jpg"
        assert fixture_path.exists()

        with open(fixture_path, "rb") as f:
            image_bytes = f.read()

        files = {"file": ("sample_passport.jpg", io.BytesIO(image_bytes), "image/jpeg")}
        data = {"lang": "en"}

        resp = await client.post(
            "/api/v2/ocr/recognize",
            files=files,
            data=data,
        )
        # No auth token → 401 or 403 (depends on security implementation)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without auth, got {resp.status_code}: {resp.text}"
        )