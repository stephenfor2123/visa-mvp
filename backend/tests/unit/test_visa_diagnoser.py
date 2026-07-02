"""VisaDiagnoser completeness rules — W36 regression.

Before W36, `_REQUIRED` only recognized `material_type == "other"` for
financial/itinerary requirements. The material wizard now tags these with
specific types (bank/flight/hotel), which used to be reported as "missing"
even when genuinely uploaded. These tests lock in the fix.
"""
from __future__ import annotations

from app.services.visa_diagnoser import VisaDiagnoser


def _material(material_type: str, mid: int = 1) -> dict:
    return {"id": mid, "material_type": material_type, "ocr_status": "done", "ocr_result": None}


class TestFinancialRequirementAcceptsBankType:
    def test_bank_type_satisfies_us_financial(self):
        materials = [_material("passport"), _material("photo"), _material("form"), _material("bank")]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "us.financial" not in codes

    def test_other_type_still_satisfies_us_financial(self):
        # Backward-compat: generic "other" upload must still count.
        materials = [_material("passport"), _material("photo"), _material("form"), _material("other")]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "us.financial" not in codes

    def test_missing_financial_still_flagged(self):
        materials = [_material("passport"), _material("photo"), _material("form")]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "us.financial" in codes


class TestItineraryRequirementAcceptsFlightHotelTypes:
    def test_flight_type_satisfies_us_itinerary(self):
        materials = [_material("passport"), _material("photo"), _material("form"), _material("flight")]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "us.itinerary" not in codes

    def test_hotel_type_satisfies_jp_itinerary(self):
        materials = [_material("passport"), _material("photo"), _material("form"), _material("hotel")]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="JP", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "jp.itinerary" not in codes


class TestPassportExpiryReadsFlatOcrResult:
    """W39 regression: the only code path that persists Material.ocr_result
    (POST /materials/{id}/ocr) writes a FLAT dict, e.g. {"expiry": "2030-12-31",
    "passport_no": "..."}. VisaDiagnoser used to read ocr_result["fields"]
    (a nested shape no producer ever wrote), so ocr_fields was always {} and
    every passport was flagged as missing its expiry even when OCR found one.
    """

    def test_flat_ocr_result_with_expiry_does_not_flag_missing(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "passport.expiry_missing" not in codes

    def test_missing_expiry_still_flagged_with_params(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678"}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        issue = next(i for i in out.issues if i.code == "passport.expiry_missing")
        assert issue.related_material_id == 1

    def test_short_expiry_flagged_with_structured_params(self):
        # W39: title/detail used to be pre-rendered zh-CN only; params lets a
        # frontend re-render the message in its own locale.
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2026-08-01"}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        issue = next(i for i in out.issues if i.code == "passport.expiry_short")
        assert issue.params["expiry"] == "2026-08-01"
        assert issue.params["min_months"] == VisaDiagnoser.PASSPORT_MIN_VALIDITY_MONTHS
        assert isinstance(issue.params["months_left"], int)


class TestPassportNotDetectedVsExpiryMissing:
    """W45: OCR finding nothing passport-like in the image (is_passport_doc
    False) is a different failure from OCR reading a real passport page but
    missing the expiry field — users were confused by the generic
    "expiry field missing" message when the upload wasn't a passport at all.
    """

    def test_is_passport_doc_false_uses_not_detected_code(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"is_passport_doc": False, "raw_text": ""}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "passport.not_detected" in codes
        assert "passport.expiry_missing" not in codes

    def test_is_passport_doc_true_but_no_expiry_uses_expiry_missing_code(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"is_passport_doc": True, "passport_no": "E12345678"}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "passport.expiry_missing" in codes
        assert "passport.not_detected" not in codes

    def test_missing_is_passport_doc_key_defaults_to_expiry_missing(self):
        # backward-compat: older persisted ocr_result rows never had this key
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678"}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "passport.expiry_missing" in codes
