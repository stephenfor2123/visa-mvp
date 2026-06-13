"""Unit tests for app.services.validation — V2 §5.2 ValidationEngine.

Covers every rule type at least once (≥ 12 cases, mostly way more).

Rule types:
  - expiry         (test_expiry_*)
  - regex          (test_regex_*)
  - length         (test_length_*)
  - date           (test_date_*)
  - age            (test_age_*)
  - file           (test_file_*)
  - image_quality  (test_image_quality_*)
  - cross_field    (test_cross_field_*)
  - ocr_confidence (test_ocr_confidence_*)
  - engine meta    (test_engine_load, test_engine_summary, ...)

The engine is a pure function — no DB, no HTTP, no real files needed.
We craft file_meta dicts by hand to simulate what the endpoint layer
will produce with PIL/cv2.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.services.validation import (
    DEFAULT_RULES_PATH,
    ValidationEngine,
)


# ---------------------------------------------------------------- #
# Fixtures                                                          #
# ---------------------------------------------------------------- #
@pytest.fixture(scope="module")
def engine() -> ValidationEngine:
    """The full bundled ruleset from app/core/validation_rules.json."""
    return ValidationEngine.from_default()


def _future_date(months: int) -> str:
    """Return YYYY-MM-DD for today + N months (clamped to month end)."""
    today = date.today()
    target_year = today.year + (today.month - 1 + months) // 12
    target_month = (today.month - 1 + months) % 12 + 1
    # clamp day to last day of target month
    if target_month == 12:
        next_month_first = date(target_year + 1, 1, 1)
    else:
        next_month_first = date(target_year, target_month + 1, 1)
    last_day = (next_month_first - timedelta(days=1)).day
    day = min(today.day, last_day)
    return date(target_year, target_month, day).isoformat()


def _past_date(years: int) -> str:
    """Return YYYY-MM-DD for today - N years."""
    today = date.today()
    try:
        return today.replace(year=today.year - years).isoformat()
    except ValueError:
        # Feb 29 edge: fall back to Feb 28
        return today.replace(year=today.year - years, day=28).isoformat()


def _good_file_meta() -> dict:
    """A passing file_meta: 1200x900 JPEG, sharp, 500 KB."""
    return {
        "mime_type": "image/jpeg",
        "size_bytes": 500_000,
        "width": 1200,
        "height": 900,
        "blur_laplacian_var": 350.0,
        "face_detected": True,
        "face_ratio": 0.35,
        "bg_color": "white",
    }


# ---------------------------------------------------------------- #
# Engine loading + introspection                                   #
# ---------------------------------------------------------------- #
class TestEngineLoad:
    def test_default_path_exists_and_is_json_array(self):
        """The bundled ruleset file exists and is a JSON list of ≥ 15 rules."""
        assert DEFAULT_RULES_PATH.is_file(), f"missing {DEFAULT_RULES_PATH}"
        data = json.loads(DEFAULT_RULES_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 15, f"need ≥ 15 rules, got {len(data)}"
        # Every rule has the required shape
        for r in data:
            for key in ("code", "rule_type", "severity", "params", "enabled", "message_key"):
                assert key in r, f"rule {r.get('code')!r} missing key {key!r}"

    def test_load_from_default_engine_has_all_codes(self, engine: ValidationEngine):
        codes = engine.enabled_rule_codes()
        # 2 are disabled (PHOTO_FACE_DETECTED + PHOTO_BG_COLOR)
        # 16 total, 14 enabled
        assert len(codes) == 14, f"expected 14 enabled rules, got {codes}"
        assert "PASSPORT_EXPIRY_MIN_6M" in codes
        assert "PASSPORT_EXPIRY_MIN_3M" in codes
        assert "PASSPORT_NO_FORMAT" in codes
        assert "PASSPORT_DOB_NOT_FUTURE" in codes
        assert "PASSPORT_DOB_AGE_MIN_16" in codes
        assert "IMAGE_BLUR_THRESHOLD" in codes
        assert "IMAGE_RESOLUTION_MIN" in codes
        assert "IMAGE_FILE_SIZE_MAX" in codes
        assert "IMAGE_FORMAT_ALLOWED" in codes
        assert "PASSPORT_NAME_MIN_LEN" in codes
        assert "TRAVEL_DATE_RANGE" in codes
        assert "STAY_DAYS_MAX" in codes
        assert "ENROLLMENT_LETTER_DATE" in codes
        assert "OCR_FIELD_CONFIDENCE" in codes
        # Disabled ones should NOT appear
        assert "PHOTO_FACE_DETECTED" not in codes
        assert "PHOTO_BG_COLOR" not in codes

    def test_unknown_rule_type_raises(self, tmp_path: Path):
        bad = [{"code": "X", "rule_type": "no_such_type", "severity": "error",
                "params": {}, "enabled": True, "message_key": "x"}]
        with pytest.raises(ValueError, match="unknown rule_type"):
            ValidationEngine(rules=bad)

    def test_from_json_file_rejects_non_list(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text('{"not": "a list"}')
        with pytest.raises(ValueError, match="must be a list"):
            ValidationEngine.from_json_file(f)


# ---------------------------------------------------------------- #
# expiry rule                                                       #
# ---------------------------------------------------------------- #
class TestExpiryRule:
    def test_passport_with_12_months_remaining_passes(self, engine):
        fields = {"expiry": _future_date(12)}
        fails = engine.run(fields)
        expiry_codes = [f["code"] for f in fails if "EXPIRY" in f["code"]]
        assert expiry_codes == [], f"unexpected expiry failures: {expiry_codes}"

    def test_passport_with_4_months_remaining_fails_6m_but_passes_3m(self, engine):
        # 4 months < 6m (error) but >= 3m (warning passes)
        fields = {"expiry": _future_date(4)}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "PASSPORT_EXPIRY_MIN_6M" in codes
        assert "PASSPORT_EXPIRY_MIN_3M" not in codes

    def test_passport_with_2_months_remaining_fails_both(self, engine):
        fields = {"expiry": _future_date(2)}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "PASSPORT_EXPIRY_MIN_6M" in codes
        assert "PASSPORT_EXPIRY_MIN_3M" in codes

    def test_passport_already_expired_fails(self, engine):
        fields = {"expiry": _past_date(1)}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "PASSPORT_EXPIRY_MIN_6M" in codes

    def test_passport_missing_expiry_field_fails(self, engine):
        fails = engine.run({})
        codes = {f["code"] for f in fails}
        assert "PASSPORT_EXPIRY_MIN_6M" in codes


# ---------------------------------------------------------------- #
# regex rule                                                        #
# ---------------------------------------------------------------- #
class TestRegexRule:
    def test_valid_chinese_passport_no_passes(self, engine):
        # Chinese passport: 1 letter + 8 digits
        fields = {"passport_no": "E12345678"}
        fails = engine.run(fields)
        assert all(f["code"] != "PASSPORT_NO_FORMAT" for f in fails)

    def test_valid_us_passport_no_passes(self, engine):
        # US passport: 9 digits
        fields = {"passport_no": "123456789"}
        fails = engine.run(fields)
        assert all(f["code"] != "PASSPORT_NO_FORMAT" for f in fails)

    def test_invalid_passport_no_lowercase_fails(self, engine):
        fields = {"passport_no": "e12345678"}  # lowercase — pattern requires uppercase
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "PASSPORT_NO_FORMAT" in codes

    def test_invalid_passport_no_wrong_length_fails(self, engine):
        fields = {"passport_no": "E12345"}  # too short
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "PASSPORT_NO_FORMAT" in codes


# ---------------------------------------------------------------- #
# length rule                                                       #
# ---------------------------------------------------------------- #
class TestLengthRule:
    def test_valid_names_pass(self, engine):
        fields = {"surname": "WANG", "given_name": "XIAOMING"}
        fails = engine.run(fields)
        assert all(f["code"] != "PASSPORT_NAME_MIN_LEN" for f in fails)

    def test_empty_given_name_fails(self, engine):
        fields = {"surname": "WANG", "given_name": ""}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "PASSPORT_NAME_MIN_LEN" in codes

    def test_oversized_name_fails(self, engine):
        fields = {"surname": "W" * 200, "given_name": "XIAOMING"}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "PASSPORT_NAME_MIN_LEN" in codes


# ---------------------------------------------------------------- #
# date rule                                                         #
# ---------------------------------------------------------------- #
class TestDateRule:
    def test_dob_in_past_passes(self, engine):
        fields = {"dob": _past_date(30)}
        fails = engine.run(fields)
        # Could still fail on age_min_16, but NOT on dob_past
        assert all(f["code"] != "PASSPORT_DOB_NOT_FUTURE" for f in fails)

    def test_dob_in_future_fails(self, engine):
        # Tomorrow is in the future
        fields = {"dob": _future_date(1)}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "PASSPORT_DOB_NOT_FUTURE" in codes

    def test_travel_date_in_past_fails(self, engine):
        fields = {"travel_date": _past_date(1)}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "TRAVEL_DATE_RANGE" in codes

    def test_travel_date_far_future_fails_365d_cap(self, engine):
        # 2 years out — exceeds max_days_future=365
        fields = {"travel_date": _future_date(24)}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "TRAVEL_DATE_RANGE" in codes

    def test_enrollment_letter_old_fails_90d_cap(self, engine):
        # 6 months old — exceeds max_age_days=90
        fields = {"enrollment_letter_date": _past_date(0)[:4] + "-01-01"}  # 2026-01-01 (old)
        # Force a date that's > 90 days old
        old = (date.today() - timedelta(days=120)).isoformat()
        fields = {"enrollment_letter_date": old}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "ENROLLMENT_LETTER_DATE" in codes


# ---------------------------------------------------------------- #
# age rule                                                          #
# ---------------------------------------------------------------- #
class TestAgeRule:
    def test_adult_passes(self, engine):
        fields = {"dob": _past_date(30)}
        fails = engine.run(fields)
        assert all(f["code"] != "PASSPORT_DOB_AGE_MIN_16" for f in fails)

    def test_minor_fails(self, engine):
        fields = {"dob": _past_date(10)}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "PASSPORT_DOB_AGE_MIN_16" in codes

    def test_16_year_old_passes(self, engine):
        # Someone born 16 years + a few months ago is unambiguously 16+ — passes
        sixteen = (date.today() - timedelta(days=16 * 365 + 30)).isoformat()
        fields = {"dob": sixteen}
        fails = engine.run(fields)
        assert all(f["code"] != "PASSPORT_DOB_AGE_MIN_16" for f in fails)


# ---------------------------------------------------------------- #
# file rule                                                         #
# ---------------------------------------------------------------- #
class TestFileRule:
    def test_good_file_passes(self, engine):
        fails = engine.run({}, file_meta=_good_file_meta())
        assert all(f["code"] != "IMAGE_FILE_SIZE_MAX" for f in fails)
        assert all(f["code"] != "IMAGE_FORMAT_ALLOWED" for f in fails)

    def test_oversized_file_fails(self, engine):
        meta = _good_file_meta()
        meta["size_bytes"] = 20 * 1024 * 1024  # 20 MB > 10 MB cap
        fails = engine.run({}, file_meta=meta)
        codes = {f["code"] for f in fails}
        assert "IMAGE_FILE_SIZE_MAX" in codes

    def test_disallowed_mime_fails(self, engine):
        meta = _good_file_meta()
        meta["mime_type"] = "image/bmp"
        fails = engine.run({}, file_meta=meta)
        codes = {f["code"] for f in fails}
        assert "IMAGE_FORMAT_ALLOWED" in codes

    def test_no_file_meta_passes_file_rule(self, engine):
        # No file uploaded → file rule is a no-op (handled by endpoint)
        fails = engine.run({})
        assert all(f["code"] != "IMAGE_FILE_SIZE_MAX" for f in fails)
        assert all(f["code"] != "IMAGE_FORMAT_ALLOWED" for f in fails)


# ---------------------------------------------------------------- #
# image_quality rule                                                #
# ---------------------------------------------------------------- #
class TestImageQualityRule:
    def test_good_image_passes(self, engine):
        fails = engine.run({}, file_meta=_good_file_meta())
        assert all(f["code"] != "IMAGE_BLUR_THRESHOLD" for f in fails)
        assert all(f["code"] != "IMAGE_RESOLUTION_MIN" for f in fails)

    def test_blurry_image_fails(self, engine):
        meta = _good_file_meta()
        meta["blur_laplacian_var"] = 50.0  # < 100 threshold
        fails = engine.run({}, file_meta=meta)
        codes = {f["code"] for f in fails}
        assert "IMAGE_BLUR_THRESHOLD" in codes

    def test_low_resolution_fails(self, engine):
        meta = _good_file_meta()
        meta["width"] = 400
        meta["height"] = 300
        fails = engine.run({}, file_meta=meta)
        codes = {f["code"] for f in fails}
        assert "IMAGE_RESOLUTION_MIN" in codes


# ---------------------------------------------------------------- #
# cross_field rule                                                  #
# ---------------------------------------------------------------- #
class TestCrossFieldRule:
    def test_short_stay_passes(self, engine):
        arrival = date.today().isoformat()
        departure = (date.today() + timedelta(days=10)).isoformat()
        fields = {"arrival_date": arrival, "departure_date": departure}
        fails = engine.run(fields)
        assert all(f["code"] != "STAY_DAYS_MAX" for f in fails)

    def test_long_stay_warns(self, engine):
        arrival = date.today().isoformat()
        departure = (date.today() + timedelta(days=120)).isoformat()
        fields = {"arrival_date": arrival, "departure_date": departure}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "STAY_DAYS_MAX" in codes
        # And the failure must be a warning, not an error
        fail = next(f for f in fails if f["code"] == "STAY_DAYS_MAX")
        assert fail["severity"] == "warning"

    def test_departure_before_arrival_fails(self, engine):
        arrival = (date.today() + timedelta(days=10)).isoformat()
        departure = date.today().isoformat()
        fields = {"arrival_date": arrival, "departure_date": departure}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "STAY_DAYS_MAX" in codes

    def test_missing_field_fails(self, engine):
        fails = engine.run({"arrival_date": "2026-01-01"})  # no departure
        codes = {f["code"] for f in fails}
        assert "STAY_DAYS_MAX" in codes


# ---------------------------------------------------------------- #
# ocr_confidence rule                                               #
# ---------------------------------------------------------------- #
class TestOcrConfidenceRule:
    def test_all_above_threshold_passes(self, engine):
        fields = {"__ocr__": {"passport_no": 0.95, "dob": 0.88, "surname": 0.92}}
        fails = engine.run(fields)
        assert all(f["code"] != "OCR_FIELD_CONFIDENCE" for f in fails)

    def test_low_confidence_field_flagged(self, engine):
        fields = {"__ocr__": {"passport_no": 0.95, "dob": 0.42}}
        fails = engine.run(fields)
        codes = {f["code"] for f in fails}
        assert "OCR_FIELD_CONFIDENCE" in codes

    def test_no_ocr_data_is_noop(self, engine):
        # Without __ocr__ key, the rule is silently skipped
        fails = engine.run({})
        assert all(f["code"] != "OCR_FIELD_CONFIDENCE" for f in fails)


# ---------------------------------------------------------------- #
# Engine-level helpers                                              #
# ---------------------------------------------------------------- #
class TestEngineSummary:
    def test_summary_counts_errors_and_warnings(self, engine):
        fields = {
            "expiry": _future_date(2),       # 2 expiry errors
            "passport_no": "bad",            # regex error
            "surname": "WANG", "given_name": "",  # length error
            "dob": _future_date(1),          # date error
            "arrival_date": date.today().isoformat(),
            "departure_date": (date.today() + timedelta(days=120)).isoformat(),
            # cross_field warning
        }
        fails = engine.run(fields)
        s = engine.summary(fails)
        assert s["errors"] >= 4
        assert s["warnings"] >= 2  # expiry_min_3m, travel (none here), stay_max
        assert s["total"] == len(fails)

    def test_has_blocking_failures_true_when_error_present(self, engine):
        fields = {"expiry": _past_date(1)}
        fails = engine.run(fields)
        assert engine.has_blocking_failures(fails) is True

    def test_has_blocking_failures_false_for_warnings_only(self, engine):
        # Build a rule set that only contains a warning
        rules = [{
            "code": "WARN_ONLY",
            "rule_type": "regex",
            "severity": "warning",
            "params": {"field": "x", "pattern": "^A$"},
            "enabled": True,
            "message_key": "x",
        }]
        eng = ValidationEngine(rules=rules)
        fails = eng.run({"x": "B"})
        assert fails and fails[0]["severity"] == "warning"
        assert eng.has_blocking_failures(fails) is False

    def test_full_happy_path_yields_no_failures(self, engine):
        fields = {
            "expiry": _future_date(24),          # 24 months > 6
            "passport_no": "E12345678",
            "surname": "WANG",
            "given_name": "XIAOMING",
            "dob": _past_date(30),
            "travel_date": (date.today() + timedelta(days=30)).isoformat(),
            "arrival_date": date.today().isoformat(),
            "departure_date": (date.today() + timedelta(days=10)).isoformat(),
            "enrollment_letter_date": date.today().isoformat(),
            "__ocr__": {"passport_no": 0.99, "dob": 0.95, "surname": 0.98},
        }
        fails = engine.run(fields, file_meta=_good_file_meta())
        assert fails == [], f"unexpected failures: {fails}"
