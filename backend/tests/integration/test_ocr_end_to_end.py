"""OCR end-to-end integration tests — V2 §5.1.

Validates the full chain:
  1. PaddleOCR recognizes a passport image fixture
  2. Field extraction populates passport_no / surname / given_name / etc.
  3. Extracted fields are written into orders.applicant_data via the
     normal create-order API path
  4. GET /api/v2/orders/{order_no} returns the OCR-derived fields
  5. 9 country fixtures (US/JP/GB/AU/SG/DE/FR/IT/KR) are each runnable
     through the same pipeline

Coverage:
  - test_ocr_full_pipeline                : US passport, end-to-end via HTTP
  - test_ocr_9_countries_parametrize      : 9 country fixtures, OCR + extract
  - test_ocr_field_extraction_accuracy    : US passport_no format + name asserts
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

# cv2 (opencv-python) and paddleocr are heavy optional deps; skip the entire
# module if they are not installed in the current venv.
pytest.importorskip("cv2", reason="opencv-python not installed; skip OCR e2e")
pytest.importorskip("paddleocr", reason="paddleocr not installed; skip OCR e2e")

import cv2  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models.destination import VisaDestination  # noqa: E402
from app.services.ocr import OCREngine  # noqa: E402

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"

# 9 countries with expected passport_no values that must be extracted.
COUNTRIES_9 = [
    ("US", "A12345678", "DOE",      "JOHN"),
    ("JP", "TR1234567",  "TANAKA",   "HIRO"),
    ("GB", "123456789",  "SMITH",    "OLIVER"),
    ("AU", "A1234567",   "WILLIAMS", "LIAM"),
    ("SG", "A1234567B",  "TAN",      "WEI"),
    ("DE", "C12345678",  "MUELLER",  "HANS"),
    ("FR", "12AB34567",  "DUPONT",   "PIERRE"),
    ("IT", "YA1234567",  "ROSSI",    "MARCO"),
    ("KR", "M12345678",  "KIM",      "MINJUN"),
]


# --------------------------------------------------------------------------- #
# Helpers — same pattern as test_orders.py                                    #
# --------------------------------------------------------------------------- #
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG-PAYLOAD" * 32


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client: AsyncClient, phone: str) -> str:
    """SMS-login → access token (mock SMS auto-registers on first use)."""
    r = await client.post(
        "/api/v2/auth/sms-login",
        json={"phone": phone, "phone_country": "+86", "sms_code": "123456"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _upload_material(client: AsyncClient, token: str, mat_type: str = "passport") -> int:
    """Upload one material via the real endpoint and return its id."""
    files = {"file": (f"{mat_type}.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
    r = await client.post(
        "/api/v2/materials/upload",
        files=files,
        data={"material_type": mat_type},
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["material"]["id"]


async def _seed_destination(country_code: str = "US") -> int:
    """Insert a VisaDestination row directly via the test DB session."""
    import json

    async with AsyncSessionLocal() as s:
        existing = await s.scalar(
            select(VisaDestination).where(
                VisaDestination.country_code == country_code
            )
        )
        if existing is not None:
            existing.enabled = True
            existing.visa_types = json.dumps(["tourism", "student"])
            await s.commit()
            return existing.id
        dest = VisaDestination(
            country_code=country_code,
            country_name_i18n=json.dumps(
                {"zh-CN": country_code, "en": country_code}, ensure_ascii=False
            ),
            visa_types=json.dumps(["tourism", "student"]),
            enabled=True,
            display_order=10,
        )
        s.add(dest)
        await s.commit()
        await s.refresh(dest)
        return dest.id


def _load_fixture_as_bgr(code: str) -> "np.ndarray":
    """Load a country fixture and return it as cv2 BGR numpy array."""
    import numpy as np
    from PIL import Image

    p = FIXTURE_DIR / f"sample_{code.lower()}_passport.jpg"
    assert p.exists(), f"fixture not found: {p}"
    img = Image.open(p).convert("RGB")
    arr = np.array(img)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


# --------------------------------------------------------------------------- #
# Test 1: Full pipeline (US) — HTTP recognize → field extraction → create order #
# --------------------------------------------------------------------------- #
class TestOCRFullPipeline:
    async def test_ocr_full_pipeline(self, client: AsyncClient):
        """
        End-to-end:
          1. Register user via SMS
          2. Upload US passport fixture to /api/v2/ocr/recognize
          3. Receive extracted fields (passport_no, surname, given_name, ...)
          4. Create an order with applicant_data populated from OCR fields
          5. GET /api/v2/orders/{order_no} → verify fields round-trip
        """
        token = await _register(client, "13855550090")
        dest_id = await _seed_destination("US")

        # 1) Upload fixture to OCR endpoint
        fixture_path = FIXTURE_DIR / "sample_us_passport.jpg"
        with open(fixture_path, "rb") as f:
            image_bytes = f.read()
        files = {
            "file": (
                "sample_us_passport.jpg",
                io.BytesIO(image_bytes),
                "image/jpeg",
            )
        }
        data = {"lang": "en"}
        r = await client.post(
            "/api/v2/ocr/recognize",
            files=files,
            data=data,
            headers=_bearer(token),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "1000", body
        ocr_result = body["data"]
        fields = ocr_result["fields"]
        assert fields["passport_no"] == "A12345678", fields
        assert fields["sex"] == "M", fields
        assert ocr_result["lang"] == "en"

        # Surname / given_name are not in the engine's structured extractor
        # (only passport_no / sex / nationality / dob / expiry are extracted).
        # We verify they appear in the raw OCR text instead.
        raw_text_upper = fields.get("raw_text", "").upper()
        assert "DOE" in raw_text_upper, f"surname 'DOE' not in raw_text: {raw_text_upper[:200]}"
        assert "JOHN" in raw_text_upper, f"given_name 'JOHN' not in raw_text: {raw_text_upper[:200]}"

        # 2) Upload a material (required to create an order)
        mid = await _upload_material(client, token, "passport")

        # 3) Create an order with applicant_data seeded from OCR fields
        # Surname + given_name are derived from raw_text lookup (engine
        # populates raw_text; the test extracts names heuristically).
        import re as _re
        surname_m = _re.search(r"SURNAME[:\s]+(\w+)", fields.get("raw_text", ""), _re.IGNORECASE)
        given_m = _re.search(r"GIVEN\s*NAME[:\s]+(\w+)", fields.get("raw_text", ""), _re.IGNORECASE)
        applicant_data = {
            "source": "ocr",
            "country_code": "US",
            "passport_no": fields["passport_no"],
            "surname": surname_m.group(1).upper() if surname_m else None,
            "given_name": given_m.group(1).upper() if given_m else None,
            "sex": fields["sex"],
            "nationality": fields.get("nationality"),
            "dob": fields.get("dob"),
            "expiry": fields.get("expiry"),
        }
        create_resp = await client.post(
            "/api/v2/orders",
            json={
                "destination_id": dest_id,
                "visa_type": "tourism",
                "material_ids": [mid],
                "applicant_data": applicant_data,
            },
            headers=_bearer(token),
        )
        assert create_resp.status_code == 201, create_resp.text
        order_no = create_resp.json()["data"]["order_no"]

        # 4) GET order detail and verify OCR fields round-trip
        detail_resp = await client.get(
            f"/api/v2/orders/{order_no}",
            headers=_bearer(token),
        )
        assert detail_resp.status_code == 200, detail_resp.text
        detail = detail_resp.json()["data"]
        assert detail["applicant_data"]["source"] == "ocr"
        assert detail["applicant_data"]["passport_no"] == "A12345678"
        assert detail["applicant_data"]["surname"] == "DOE"
        assert detail["applicant_data"]["given_name"] == "JOHN"
        assert detail["applicant_data"]["sex"] == "M"
        assert detail["applicant_data"]["country_code"] == "US"


# --------------------------------------------------------------------------- #
# Test 2: 9 countries parametrize                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "code,expected_pn,expected_surname,expected_given_name",
    COUNTRIES_9,
    ids=[c[0] for c in COUNTRIES_9],
)
class TestOCR9Countries:
    async def test_ocr_9_countries_parametrize(
        self,
        code: str,
        expected_pn: str,
        expected_surname: str,
        expected_given_name: str,
    ):
        """
        For each of the 9 country fixtures:
          - Load fixture
          - Run OCREngine.recognize + extract_passport_fields
          - Assert passport_no is extracted correctly
          - Assert surname + given_name are present in raw text
        """
        engine = OCREngine(lang="en")
        img_bgr = _load_fixture_as_bgr(code)
        fields = engine.extract_passport_fields(img_bgr)

        # passport_no must be the exact expected value
        assert fields["passport_no"] == expected_pn, (
            f"[{code}] expected={expected_pn}, got={fields['passport_no']}, "
            f"raw_text={fields.get('raw_text', '')[:120]}"
        )

        # surname + given_name should be present somewhere in the OCR text
        # (the heuristic extractor doesn't pick them out as separate fields,
        # but the raw_text must contain them)
        raw = fields.get("raw_text", "").upper().replace(" ", "")
        assert expected_surname.upper() in raw, (
            f"[{code}] surname '{expected_surname}' not in OCR text: {raw[:200]}"
        )
        assert expected_given_name.upper() in raw, (
            f"[{code}] given_name '{expected_given_name}' not in OCR text: {raw[:200]}"
        )

        # sex + nationality should also be set
        assert fields.get("sex") == "M", f"[{code}] sex extraction: {fields.get('sex')}"


# --------------------------------------------------------------------------- #
# Test 3: US passport_no format + accuracy asserts                           #
# --------------------------------------------------------------------------- #
class TestOCRFieldExtractionAccuracy:
    def test_ocr_field_extraction_accuracy(self):
        """
        US passport fixture:
          - passport_no = A[0-9]{8} (1 letter + 8 digits, total 9 chars)
          - surname / given_name non-empty
          - sex parsed
          - at least 1 date extracted
        """
        engine = OCREngine(lang="en")
        img_bgr = _load_fixture_as_bgr("US")
        fields = engine.extract_passport_fields(img_bgr)

        # passport_no format
        pn = fields["passport_no"]
        assert pn is not None, f"passport_no is None: {fields}"
        assert re.fullmatch(r"A[0-9]{8}", pn), (
            f"US passport_no must match A[0-9]{{8}}, got: {pn}"
        )
        assert len(pn) == 9, f"US passport_no must be 9 chars, got {len(pn)}: {pn}"

        # Names present in raw text
        raw = fields.get("raw_text", "").upper().replace(" ", "")
        assert "DOE" in raw, f"surname 'DOE' not in raw_text: {raw[:200]}"
        assert "JOHN" in raw, f"given_name 'JOHN' not in raw_text: {raw[:200]}"

        # sex
        assert fields.get("sex") in ("M", "F"), f"sex invalid: {fields.get('sex')}"

        # At least one date (DOB or expiry)
        assert fields.get("dob") is not None or fields.get("expiry") is not None, (
            f"no date extracted: {fields}"
        )

        # raw_text non-empty
        assert len(fields.get("raw_text", "")) > 20, (
            f"raw_text too short: {len(fields.get('raw_text', ''))} chars"
        )
