"""Unit tests for app.core.ds160 (W48 v0.2).

Coverage:
  - generate_code: format + uniqueness + charset (no 0/O/1/I/L/U)
  - normalize_code_input: strip dashes / spaces / lowercase → uppercase
  - is_valid_code_format: positive + negative cases
  - load_applicant_profile: lenient parsing of Order.applicant_data JSON
  - normalize_date: ISO / DD/MM/YYYY / DD MMM YYYY / unparseable
  - compute_fingerprint: stability, avalanche, case/whitespace insensitivity,
    date normalization, untouched sections
  - InMemoryRateLimiter: per-key sliding window
  - has_minimum_fields: returns False on bare applicant_data
"""
from __future__ import annotations

import json
import re

import pytest

from app.core.ds160 import (
    ApplicantProfile,
    InMemoryRateLimiter,
    _DS160_ALPHABET,
    compute_fingerprint,
    generate_code,
    has_minimum_fields,
    is_valid_code_format,
    load_applicant_profile,
    normalize_code_input,
    normalize_date,
)


# --------------------------------------------------------------------------- #
# generate_code / is_valid_code_format / normalize_code_input                 #
# --------------------------------------------------------------------------- #

class TestDs160EnumsConsistency:
    """Sanity checks that the shared enums (frontend mirror) cover the keys
    fillEngine expects to find when matching against the official DS-160
    select values.  These tests don't exercise the frontend — they just guard
    the data source so a typo doesn't silently break the chrome extension.
    """

    @pytest.mark.parametrize("iso2,expected", [
        ("VN", "VIETNAM"),
        ("ID", "INDONESIA"),
        ("CN", "CHINA, PEOPLE'S REPUBLIC OF"),
        ("US", "UNITED STATES"),
        ("GB", "UNITED KINGDOM"),
        ("TH", "THAILAND"),
        ("MY", "MALAYSIA"),
        ("PH", "PHILIPPINES"),
        ("KH", "CAMBODIA"),
        ("LA", "LAO PEOPLE'S DEMOCRATIC REPUBLIC"),
    ])
    def test_country_iso_to_dropsown(self, iso2, expected):
        # Read the enums file from the frontend dist; the values should be
        # readable from Python by parsing the exported `DS160_COUNTRIES` map.
        from pathlib import Path
        import re
        # Path layout: backend/tests/unit/test_ds160.py
        #   parents[0] = unit, parents[1] = tests, parents[2] = backend, parents[3] = project root
        enum_path = Path(__file__).resolve().parents[3] / "frontend" / "web" / "src" / "data" / "ds160Enums.js"
        if not enum_path.exists():
            pytest.skip("ds160Enums.js not present (frontend source not in this checkout)")
        src = enum_path.read_text(encoding="utf-8")
        # Value may contain apostrophes (e.g. "CHINA, PEOPLE'S REPUBLIC OF"), so we
        # can't use [^']+; instead find the line, then parse backslash-escaped quotes.
        line_m = re.search(rf"\b{iso2}\s*:\s*'(.*?)',?\s*$", src, re.MULTILINE)
        assert line_m is not None, f"ISO {iso2} missing from DS160_COUNTRIES"
        raw = line_m.group(1)
        # Unescape: only \', \\\, \n in our source file
        unescaped = raw.replace("\\'", "'").replace("\\\\", "\\")
        assert unescaped == expected, (
            f"ISO {iso2} maps to {unescaped!r}, expected {expected!r}"
        )

    def test_special_china_variants_present(self):
        """DS-160 把中国拆成多个选项, 5 个都要有."""
        from pathlib import Path
        import re
        enum_path = Path(__file__).resolve().parents[3] / "frontend" / "web" / "src" / "data" / "ds160Enums.js"
        src = enum_path.read_text(encoding="utf-8")
        for key, expected in [
            ("CN", "CHINA, PEOPLE'S REPUBLIC OF"),
            ("CN_MAINLAND", "CHINA-MAINLAND"),
            ("CN_HK", "CHINA, HONG KONG SAR"),
            ("CN_MACAU", "CHINA, MACAU SAR"),
            ("CN_TAIWAN", "CHINA, TAIWAN"),
        ]:
            line_m = re.search(rf"\b{key}\s*:\s*'(.*?)',?\s*$", src, re.MULTILINE)
            assert line_m is not None, f"missing {key}"
            unescaped = line_m.group(1).replace("\\'", "'").replace("\\\\", "\\")
            assert unescaped == expected, f"{key} → {unescaped}"

    def test_no_country_uses_unicode_diacritics(self):
        """DS-160 不接受 ñ é ü ç (官方明确). 国家名必须纯 ASCII."""
        from pathlib import Path
        import re
        enum_path = Path(__file__).resolve().parents[3] / "frontend" / "web" / "src" / "data" / "ds160Enums.js"
        src = enum_path.read_text(encoding="utf-8")
        for m in re.finditer(r"^\s*[A-Z0-9_]+\s*:\s*'(.*?)',?\s*$", src, re.MULTILINE):
            value = m.group(1)
            # Unescape first
            unescaped = value.replace("\\'", "'").replace("\\\\", "\\")
            # Check all characters are ASCII printable (no ñ é ü ç)
            try:
                unescaped.encode('ascii')
            except UnicodeEncodeError:
                pytest.fail(f"Enum value {unescaped!r} contains non-ASCII chars; DS-160 won't accept them")


    def test_format_is_12_base30(self):
        for _ in range(200):
            code = generate_code()
            assert len(code) == 12
            assert is_valid_code_format(code)

    def test_charset_excludes_confusable_chars(self):
        # Crockford-ish: no 0, O, 1, I, L, U
        for _ in range(200):
            code = generate_code()
            assert not re.search(r"[0O1ILU]", code), f"bad char in {code}"

    def test_unique_over_thousand(self):
        # 12-char base30 → 30^12 ≈ 5e17.  1k collisions vanishingly unlikely.
        codes = {generate_code() for _ in range(1000)}
        assert len(codes) == 1000

    def test_alphabet_size_matches_documented(self):
        assert len(_DS160_ALPHABET) == 30


class TestNormalizeCodeInput:
    def test_strips_dashes_and_spaces_and_uppercases(self):
        assert normalize_code_input("abcd-efgh-jklm") == "ABCDEFGHJKLM"
        assert normalize_code_input("  K7H3 N9XR A2BQ  ") == "K7H3N9XRA2BQ"

    def test_strips_punctuation(self):
        assert normalize_code_input("K7H3.N9XR/A2BQ") == "K7H3N9XRA2BQ"

    def test_empty_input(self):
        assert normalize_code_input("") == ""
        assert normalize_code_input(None) == ""  # type: ignore[arg-type]


class TestIsValidCodeFormat:
    def test_accepts_well_formed(self):
        assert is_valid_code_format("ABCDEFGHJKLM")
        assert is_valid_code_format("23456789ABCD")

    def test_rejects_too_short(self):
        assert not is_valid_code_format("ABC")
        assert not is_valid_code_format("")

    def test_rejects_too_long(self):
        assert not is_valid_code_format("ABCDEFGHJKLMN")

    def test_rejects_confusable_chars(self):
        assert not is_valid_code_format("ABCDEFGHJKL0")  # has 0
        assert not is_valid_code_format("ABCDEFGHJKLO")  # has O


# --------------------------------------------------------------------------- #
# load_applicant_profile                                                       #
# --------------------------------------------------------------------------- #

class TestLoadApplicantProfile:
    def test_empty_raw_returns_empty_profile(self):
        p = load_applicant_profile(None)
        assert p.identity["surname"] == ""
        assert p.passport["number"] == ""

    def test_garbage_json_returns_empty_profile(self):
        p = load_applicant_profile("not-json")
        assert isinstance(p, ApplicantProfile)
        assert p.identity["surname"] == ""

    def test_picks_known_aliases(self):
        raw = json.dumps({
            "surname": "NGUYEN",
            "given_name": "Van",
            "passport_no": "B1234567",
            "nationality": "VN",
            "birth_date": "1992-05-14",
        })
        p = load_applicant_profile(raw)
        assert p.identity["surname"] == "NGUYEN"
        assert p.identity["givenName"] == "Van"
        assert p.identity["nationality"] == "VN"
        assert p.identity["dob"] == "1992-05-14"
        assert p.passport["number"] == "B1234567"

    def test_first_non_empty_alias_wins(self):
        raw = json.dumps({
            "surname": "TRAN",          # primary alias
            "full_name": "Should Lose",  # secondary alias
        })
        p = load_applicant_profile(raw)
        assert p.identity["surname"] == "TRAN"

    def test_to_dict_roundtrip(self):
        raw = json.dumps({"surname": "X", "given_name": "Y"})
        p = load_applicant_profile(raw)
        d = p.to_dict()
        assert d["identity"]["surname"] == "X"
        assert d["identity"]["givenName"] == "Y"
        assert "passport" in d
        assert isinstance(d["family"]["spouse"], dict)

    def test_nested_family_spouse_paths(self):
        raw = json.dumps({
            "surname": "TRAN",
            "given_name": "Thi",
            "spouse_surname": "LE",
            "spouse_given_name": "MINH",
            "companion_surname": "PHAM",
            "has_companions": "YES",
        })
        p = load_applicant_profile(raw)
        assert p.family["spouse"]["surname"] == "LE"
        assert p.family["spouse"]["givenName"] == "MINH"
        assert p.travel["companion"]["surname"] == "PHAM"
        assert p.travel["hasCompanions"] is True

    def test_stay_days_formatted_for_mapping(self):
        raw = json.dumps({"stay_days": 10, "arrival_date": "2026-08-01"})
        p = load_applicant_profile(raw)
        assert p.travel["stayLength"] == "10 DAYS"
        assert p.travel["hasPlan"] is True


# --------------------------------------------------------------------------- #
# normalize_date                                                               #
# --------------------------------------------------------------------------- #

class TestNormalizeDate:
    @pytest.mark.parametrize("raw,expected", [
        ("1992-05-14", "1992-05-14"),
        ("1992/05/14", "1992-05-14"),
        ("1992.05.14", "1992-05-14"),
        ("14/05/1992", "1992-05-14"),
        ("14-05-1992", "1992-05-14"),
        ("14.05.1992", "1992-05-14"),
        ("14 MAY 1992", "1992-05-14"),
        ("14-MAY-1992", "1992-05-14"),
    ])
    def test_supported_formats(self, raw, expected):
        assert normalize_date(raw) == expected

    @pytest.mark.parametrize("raw", [
        "",
        "not-a-date",
        "1992/13/40",  # invalid month/day
    ])
    def test_unparseable_returns_empty(self, raw):
        assert normalize_date(raw) == ""

    def test_none_returns_empty(self):
        assert normalize_date(None) == ""


# --------------------------------------------------------------------------- #
# compute_fingerprint                                                          #
# --------------------------------------------------------------------------- #

def _bare_profile(**overrides) -> ApplicantProfile:
    """Construct an ApplicantProfile where every tracked field is empty by default."""
    base = load_applicant_profile("{}")
    d = base.to_dict()
    for path, val in overrides.items():
        parts = path.split(".")
        cur = d
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = val
    return ApplicantProfile(
        identity=d["identity"],
        passport=d["passport"],
        contact=d["contact"],
        travel=d["travel"],
        previous=d["previous"],
        usContact=d["usContact"],
        work=d["work"],
        family=d["family"],
        security=d["security"],
    )


class TestComputeFingerprint:
    def test_empty_profile_returns_32_hex(self):
        fp = compute_fingerprint(_bare_profile())
        assert len(fp) == 32
        assert re.match(r"^[0-9a-f]{32}$", fp)

    def test_stable_across_calls(self):
        fp1 = compute_fingerprint(_bare_profile())
        fp2 = compute_fingerprint(_bare_profile())
        assert fp1 == fp2

    def test_unicode_vietnamese_name_stable_across_whitespace(self):
        """W48 v0.2: Vietnamese names with diacritics (Nguyễn Văn An) must be
        normalized the same way regardless of leading/trailing whitespace.
        Different Unicode representations (NFC vs NFD) are NOT yet normalized —
        P1 will add unicodedata.normalize('NFC', ...) before hashing if users
        report issues from copy-pasting between keyboard input methods.
        """
        a = _bare_profile(**{"identity.surname": "Nguyễn", "identity.givenName": "Văn An"})
        b = _bare_profile(**{"identity.surname": "  Nguyễn  ", "identity.givenName": "văn an"})
        assert compute_fingerprint(a) == compute_fingerprint(b)

    def test_chinese_name_handled(self):
        """Chinese names (e.g. 王小明) preserve all characters after strip+lower."""
        a = _bare_profile(**{"identity.surname": "王", "identity.givenName": "小明"})
        b = _bare_profile(**{"identity.surname": "  王  ", "identity.givenName": "小明"})
        assert compute_fingerprint(a) == compute_fingerprint(b)

    def test_indonesian_name_stable(self):
        """Indonesian names are typically ASCII; upper-casing should be a no-op."""
        a = _bare_profile(**{"identity.surname": "Budi", "identity.givenName": "Santoso"})
        b = _bare_profile(**{"identity.surname": "BUDI", "identity.givenName": "SANTOSO"})
        # The fingerprint normalizes via lower(), so both produce the same fp.
        assert compute_fingerprint(a) == compute_fingerprint(b)

    def test_changing_any_field_changes_fingerprint(self):
        base_fp = compute_fingerprint(_bare_profile())
        # For date fields the test must use valid date strings; an unparseable
        # value normalises to "" and would not move the fingerprint (by design).
        # For everything else, the literal "NEW" suffices.
        mutations = [
            ("identity.surname", "NGUYEN"),
            ("identity.givenName", "Van"),
            ("identity.dob", "1993-06-15"),
            ("identity.nationality", "VN"),
            ("passport.number", "B9999999"),
            ("contact.street", "123 Main"),
            ("contact.city", "HCMC"),
            ("contact.email", "x@y.z"),
            ("work.employer", "Acme"),
            ("work.occupation", "Engineer"),
            ("family.father.surname", "Nguyen"),
            ("previous.hasVisited", "true"),
            ("travel.arrivalDate", "2027-01-01"),
            ("usContact.personSurname", "Smith"),
        ]
        for path, new_value in mutations:
            modified = _bare_profile(**{path: new_value})
            new_fp = compute_fingerprint(modified)
            assert new_fp != base_fp, f"changing {path} to {new_value!r} did NOT change fingerprint"

    def test_whitespace_and_case_insensitive(self):
        a = _bare_profile(**{"identity.surname": "  NGUYEN  "})
        b = _bare_profile(**{"identity.surname": "nguyen"})
        assert compute_fingerprint(a) == compute_fingerprint(b)

    def test_date_normalization_in_fingerprint(self):
        a = _bare_profile(**{"identity.dob": "1992-05-14"})
        b = _bare_profile(**{"identity.dob": "14/05/1992"})
        c = _bare_profile(**{"identity.dob": "14 MAY 1992"})
        assert compute_fingerprint(a) == compute_fingerprint(b) == compute_fingerprint(c)

    def test_unparseable_date_treated_as_empty(self):
        a = _bare_profile(**{"identity.dob": "not-a-date"})
        b = _bare_profile()  # empty
        assert compute_fingerprint(a) == compute_fingerprint(b)

    def test_missing_section_treated_as_empty(self):
        a = compute_fingerprint({})  # type: ignore[arg-type]
        b = compute_fingerprint(_bare_profile())
        assert a == b

    def test_avalanche_on_single_bit(self):
        """Changing one byte should flip roughly half the fingerprint bits."""
        a = compute_fingerprint(_bare_profile(**{"identity.surname": "A"}))
        b = compute_fingerprint(_bare_profile(**{"identity.surname": "B"}))
        diff_bits = sum(1 for x, y in zip(a, b) if x != y)
        # 32 hex chars = 128 bits; expect 40-90 by avalanche heuristic.
        assert 40 <= diff_bits * 4 <= 120

    def test_accepts_plain_dict(self):
        """Backwards-compat: passing a dict works as well as an ApplicantProfile."""
        d = _bare_profile(**{"identity.surname": "X"}).to_dict()
        fp = compute_fingerprint(d)
        assert len(fp) == 32


# --------------------------------------------------------------------------- #
# has_minimum_fields                                                           #
# --------------------------------------------------------------------------- #

class TestHasMinimumFields:
    def test_empty_profile_fails(self):
        assert has_minimum_fields(_bare_profile()) is False

    def test_only_surname_fails(self):
        p = _bare_profile(**{"identity.surname": "NGUYEN"})
        assert has_minimum_fields(p) is False

    def test_all_required_passes(self):
        p = _bare_profile(**{
            "identity.surname": "NGUYEN",
            "identity.givenName": "Van",
            "identity.dob": "1992-05-14",
            "identity.nationality": "VN",
            "passport.number": "B1234567",
        })
        assert has_minimum_fields(p) is True

    def test_blank_string_fails(self):
        p = _bare_profile(**{
            "identity.surname": "",
            "identity.givenName": "Van",
            "identity.dob": "1992-05-14",
            "identity.nationality": "VN",
            "passport.number": "B1234567",
        })
        assert has_minimum_fields(p) is False


# --------------------------------------------------------------------------- #
# InMemoryRateLimiter                                                          #
# --------------------------------------------------------------------------- #

class TestInMemoryRateLimiter:
    def test_allows_under_threshold(self):
        lim = InMemoryRateLimiter(window_sec=60)
        for _ in range(5):
            ok, _ = lim.check_and_hit({"order": "1"})
            assert ok

    def test_blocks_over_threshold(self):
        lim = InMemoryRateLimiter(
            window_sec=60,
            per_key_limits={"order": 3, "ip": 100},
        )
        assert lim.check_and_hit({"order": "1"})[0]
        assert lim.check_and_hit({"order": "1"})[0]
        assert lim.check_and_hit({"order": "1"})[0]
        ok, err = lim.check_and_hit({"order": "1"})
        assert not ok
        assert err == "RATE_LIMITED"

    def test_separate_keys_independent(self):
        lim = InMemoryRateLimiter(
            window_sec=60,
            per_key_limits={"order": 1, "ip": 100},
        )
        assert lim.check_and_hit({"order": "1"})[0]
        # order=2 should still work (independent counter)
        assert lim.check_and_hit({"order": "2"})[0]
        # order=1 now blocked
        ok, _ = lim.check_and_hit({"order": "1"})
        assert not ok

    def test_window_resets_after_expiry(self, monkeypatch):
        lim = InMemoryRateLimiter(window_sec=10, per_key_limits={"order": 1})
        assert lim.check_and_hit({"order": "1"})[0]
        ok, _ = lim.check_and_hit({"order": "1"})
        assert not ok

        # Advance "time" by monkeypatching time.monotonic
        import time as t
        original = t.monotonic
        monkeypatch.setattr(t, "monotonic", lambda: original() + 11)
        ok, _ = lim.check_and_hit({"order": "1"})
        assert ok

    def test_reset_clears_counters(self):
        lim = InMemoryRateLimiter(per_key_limits={"order": 1})
        assert lim.check_and_hit({"order": "1"})[0]
        lim.reset()
        assert lim.check_and_hit({"order": "1"})[0]