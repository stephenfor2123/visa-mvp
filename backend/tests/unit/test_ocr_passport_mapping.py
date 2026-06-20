"""Unit tests for backend/data/passport_field_mapping.yaml — W14-1.

Tests:
1. YAML loading for all 9 countries
2. Field name mapping completeness
3. Passport number regex validation (pass + reject samples)
4. expiry_min_months logic

Countries: Indonesia (ID) / Vietnam (VN) / Philippines (PH) / Thailand (TH) /
           Malaysia (MY) / Singapore (SG) / China (CN) / Japan (JP) / Korea (KR)

Note: This test file is standalone and does NOT import the app modules
to avoid pydantic architecture compatibility issues. It directly tests
the YAML file using only stdlib + pytest + pyyaml.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------- #
# Fixtures                                                          #
# ---------------------------------------------------------------- #
@pytest.fixture(scope="module")
def mapping_data() -> dict:
    """Load passport_field_mapping.yaml from data/ directory."""
    backend_root = Path(__file__).parent.parent.parent  # tests/unit -> backend
    yaml_path = backend_root / "data" / "passport_field_mapping.yaml"
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def expected_countries() -> list[str]:
    """Expected 9 country keys."""
    return ["id", "vn", "ph", "th", "my", "sg", "cn", "jp", "kr"]


# ---------------------------------------------------------------- #
# Test 1: YAML loading for all 9 countries                          #
# ---------------------------------------------------------------- #
class TestYamlLoading:
    """Test that YAML file loads successfully and contains all 9 countries."""

    def test_yaml_loads_successfully(self, mapping_data: dict) -> None:
        """YAML file should parse without errors."""
        assert mapping_data is not None
        assert isinstance(mapping_data, dict)

    def test_all_9_countries_present(self, mapping_data: dict, expected_countries: list[str]) -> None:
        """All 9 required country keys must be present."""
        for country in expected_countries:
            assert country in mapping_data, f"Missing country: {country}"

    def test_no_extra_countries(self, mapping_data: dict, expected_countries: list[str]) -> None:
        """No unexpected country keys should be present.

        W22 fix: YAML 有 nationality_map 这个 metadata key,不算 extra country
        """
        # Filter out non-country keys (anything that's not 2-letter country code)
        actual_countries = {k for k in mapping_data.keys() if len(k) == 2}
        extra = actual_countries - set(expected_countries)
        assert not extra, f"Unexpected countries: {extra}"

    def test_country_count(self, mapping_data: dict) -> None:
        """Must have exactly 9 countries."""
        # W22 fix: filter to 2-letter keys (nationality_map is metadata)
        actual_countries = {k for k in mapping_data.keys() if len(k) == 2}
        assert len(actual_countries) == 9, f"Expected 9 countries, got {len(actual_countries)}"


# ---------------------------------------------------------------- #
# Test 2: Field name mapping completeness                            #
# ---------------------------------------------------------------- #
class TestFieldMappingCompleteness:
    """Test that each country has all required fields."""

    REQUIRED_FIELDS = [
        "country_code",
        "country_name_en",
        "country_name_zh",
        "passport_number_re",
        "expiry_min_months",
        "date_fmt",
        "surname_pos",
        "given_name_pos",
        "birth_date_field",
        "expiry_date_field",
        "gender_map",
        "field_order",
    ]

    def test_all_required_fields_present(
        self, mapping_data: dict, expected_countries: list[str]
    ) -> None:
        """Each country must have all required fields."""
        for country in expected_countries:
            country_data = mapping_data[country]
            for field in self.REQUIRED_FIELDS:
                assert field in country_data, (
                    f"Country {country} missing field: {field}"
                )

    def test_country_code_format(
        self, mapping_data: dict, expected_countries: list[str]
    ) -> None:
        """country_code should be 2-letter uppercase ISO code."""
        for country in expected_countries:
            code = mapping_data[country]["country_code"]
            assert len(code) == 2, f"{country}: country_code should be 2 chars"
            assert code.isupper(), f"{country}: country_code should be uppercase"
            assert code == country.upper(), (
                f"{country}: country_code {code} should match key {country.upper()}"
            )

    def test_expiry_min_months_positive(
        self, mapping_data: dict, expected_countries: list[str]
    ) -> None:
        """expiry_min_months should be a positive integer."""
        for country in expected_countries:
            months = mapping_data[country]["expiry_min_months"]
            assert isinstance(months, int), f"{country}: expiry_min_months must be int"
            assert months > 0, f"{country}: expiry_min_months must be positive"

    def test_date_fmt_valid(
        self, mapping_data: dict, expected_countries: list[str]
    ) -> None:
        """date_fmt should be a non-empty string."""
        for country in expected_countries:
            fmt = mapping_data[country]["date_fmt"]
            assert isinstance(fmt, str), f"{country}: date_fmt must be string"
            assert len(fmt) > 0, f"{country}: date_fmt cannot be empty"

    def test_gender_map_normalizes_to_m_and_f(
        self, mapping_data: dict, expected_countries: list[str]
    ) -> None:
        """gender_map should normalize to M and F (via M->M and F->F keys)."""
        for country in expected_countries:
            gm = mapping_data[country]["gender_map"]
            assert "M" in gm, f"{country}: gender_map should include M"
            assert gm["M"] == "M", f"{country}: M should map to M"
            # All should have F normalization via F key or country-specific keys (e.g., P/L for ID)
            f_values = [v for v in gm.values() if v == "F"]
            assert f_values, f"{country}: gender_map should normalize to F"

    def test_field_order_not_empty(
        self, mapping_data: dict, expected_countries: list[str]
    ) -> None:
        """field_order should be a non-empty list."""
        for country in expected_countries:
            fo = mapping_data[country]["field_order"]
            assert isinstance(fo, list), f"{country}: field_order must be list"
            assert len(fo) > 0, f"{country}: field_order cannot be empty"


# ---------------------------------------------------------------- #
# Test 3: Passport number regex validation                           #
# ---------------------------------------------------------------- #
class TestPassportNumberRegex:
    """Test that passport number regex validates correctly."""

    # Valid passport numbers (should match)
    VALID_PASSPORTS = {
        "id": ["A12345678", "B98765432", "Z11111111"],
        "vn": ["A12345678", "B98765432", "C11111111"],
        "ph": ["P1234567A", "E1234567B", "G1234567Z"],
        "th": ["A12345678", "B98765432", "Z11111111"],
        "my": ["AA1234567", "ZZ9876543", "MM1111111"],
        "sg": ["A1234567A", "E9876543B", "G1234567Z"],
        "cn": ["A12345678", "E98765432", "G11111111"],
        "jp": ["TR1234567", "ZZ9876543", "AA1111111"],
        "kr": ["AA1234567", "ZZ9876543", "MM1111111"],
    }

    # Invalid passport numbers (should not match)
    INVALID_PASSPORTS = {
        "id": ["123456789", "ABCDEFGHI", "a12345678", "A1234567", "A123456789", "AA12345678"],
        "vn": ["123456789", "ABCDEFGHI", "a12345678", "A1234567"],
        "ph": ["123456789", "P12345678", "P1234567", "ABCDEFGH", "P12345678A"],
        "th": ["123456789", "ABCDEFGHI", "a12345678", "A1234567", "AA12345678"],
        "my": ["A1234567", "ABCDEFGH", "AAA123456", "A12345678"],
        "sg": ["123456789", "ABCDEFGHI", "A12345678", "AA1234567", "A1234567", "E1234567"],
        "cn": ["123456789", "ABCDEFGHI", "a12345678", "A1234567", "AA12345678"],
        "jp": ["A1234567", "ABCDEFGH", "123456789", "AAA1234567", "AA123456"],
        "kr": ["A1234567", "ABCDEFGH", "123456789", "AAA1234567", "AA123456"],
    }

    def test_valid_passports_match(
        self, mapping_data: dict, expected_countries: list[str]
    ) -> None:
        """Valid passport numbers should match their country's regex."""
        for country in expected_countries:
            regex = mapping_data[country]["passport_number_re"]
            pattern = re.compile(f"^{regex}$")
            valid_list = self.VALID_PASSPORTS[country]
            for passport in valid_list:
                assert pattern.fullmatch(passport), (
                    f"{country}: '{passport}' should match regex ^{regex}$"
                )

    def test_invalid_passports_rejected(
        self, mapping_data: dict, expected_countries: list[str]
    ) -> None:
        """Invalid passport numbers should not match their country's regex."""
        for country in expected_countries:
            regex = mapping_data[country]["passport_number_re"]
            pattern = re.compile(f"^{regex}$")
            invalid_list = self.INVALID_PASSPORTS[country]
            for passport in invalid_list:
                assert not pattern.fullmatch(passport), (
                    f"{country}: '{passport}' should NOT match regex ^{regex}$"
                )

    def test_regex_is_valid_pattern(
        self, mapping_data: dict, expected_countries: list[str]
    ) -> None:
        """Each passport_number_re should be a valid regex pattern."""
        for country in expected_countries:
            regex = mapping_data[country]["passport_number_re"]
            try:
                re.compile(f"^{regex}$")
            except re.error as e:
                pytest.fail(f"{country}: invalid regex pattern '{regex}': {e}")

    def test_regex_allows_lowercase_input(
        self, mapping_data: dict
    ) -> None:
        """Regex should be usable with case-insensitive matching for OCR output."""
        # Some OCR engines may return lowercase; we test that our regex
        # pattern can be made case-insensitive without breaking valid input
        for country_key, country_data in mapping_data.items():
            # W22 fix: skip non-country keys (nationality_map 等)
            if len(country_key) != 2:
                continue
            regex = country_data["passport_number_re"]
            pattern = re.compile(f"^{regex}$", re.IGNORECASE)
            # Verify the pattern still rejects obviously wrong input
            assert not pattern.fullmatch("INVALID123")
            assert not pattern.fullmatch("123456789")


# ---------------------------------------------------------------- #
# Test 4: expiry_min_months logic                                   #
# ---------------------------------------------------------------- #
class TestExpiryMinMonths:
    """Test expiry_min_months validation logic."""

    def test_expiry_min_months_is_6(
        self, mapping_data: dict, expected_countries: list[str]
    ) -> None:
        """All countries should require minimum 6 months validity."""
        for country in expected_countries:
            months = mapping_data[country]["expiry_min_months"]
            assert months == 6, (
                f"{country}: expiry_min_months should be 6, got {months}"
            )

    def test_expiry_calculation_logic(self) -> None:
        """Test the logic for checking passport expiry validity."""
        # Simulate checking if a passport with expiry date meets minimum requirement
        def is_valid_expiry(expiry_date: date, min_months: int = 6) -> bool:
            today = date.today()
            # Calculate required minimum expiry date
            required_months = min_months
            required_year = today.year + (today.month - 1 + required_months) // 12
            required_month = (today.month - 1 + required_months) % 12 + 1
            # Default to 1st of month for day calculation
            required_date = date(required_year, required_month, 1)
            return expiry_date >= required_date

        # Test cases
        today = date.today()
        six_months_later = date(
            today.year + (today.month - 1 + 6) // 12,
            (today.month - 1 + 6) % 12 + 1,
            1,
        )

        # Valid: expiry is more than 6 months from now
        assert is_valid_expiry(date(2099, 12, 31))
        assert is_valid_expiry(six_months_later)

        # Invalid: expiry is less than 6 months from now
        yesterday = date(today.year, today.month, 1)
        assert not is_valid_expiry(yesterday)
        assert not is_valid_expiry(date(2020, 1, 1))


# ---------------------------------------------------------------- #
# Test 5: Integration — load and validate the full YAML             #
# ---------------------------------------------------------------- #
class TestFullYamlIntegration:
    """End-to-end test: load YAML, validate all countries."""

    def test_all_countries_have_valid_structure(self, mapping_data: dict) -> None:
        """Full integration test: all countries pass all checks."""
        errors: list[str] = []

        # W22 fix: 只验证 2-letter country code keys, 跳过 metadata (nationality_map)
        for country_key, country_data in mapping_data.items():
            if len(country_key) != 2:
                continue
            # Check required fields
            for field in TestFieldMappingCompleteness.REQUIRED_FIELDS:
                if field not in country_data:
                    errors.append(f"{country_key}: missing {field}")

            # Check regex validity
            regex = country_data.get("passport_number_re", "")
            try:
                re.compile(f"^{regex}$")
            except re.error:
                errors.append(f"{country_key}: invalid regex '{regex}'")

            # Check expiry_min_months
            months = country_data.get("expiry_min_months", 0)
            if not isinstance(months, int) or months <= 0:
                errors.append(f"{country_key}: invalid expiry_min_months {months}")

        assert not errors, f"Validation errors: {'; '.join(errors)}"

    def test_yaml_file_exists_and_readable(self) -> None:
        """Verify the YAML file exists at the expected path."""
        backend_root = Path(__file__).parent.parent.parent
        yaml_path = backend_root / "data" / "passport_field_mapping.yaml"
        assert yaml_path.exists(), f"YAML file not found at {yaml_path}"
        assert yaml_path.is_file(), f"Path is not a file: {yaml_path}"

        # Verify it's readable
        content = yaml_path.read_text(encoding="utf-8")
        assert len(content) > 0, "YAML file is empty"

    def test_yaml_content_has_expected_size(self) -> None:
        """Verify the YAML file has been properly populated."""
        backend_root = Path(__file__).parent.parent.parent
        yaml_path = backend_root / "data" / "passport_field_mapping.yaml"
        content = yaml_path.read_text(encoding="utf-8")

        # Should have substantial content (9 countries × ~30 lines minimum)
        assert len(content) > 2000, (
            f"YAML file seems too small ({len(content)} chars). "
            "Expected >2000 chars for 9 country mappings."
        )