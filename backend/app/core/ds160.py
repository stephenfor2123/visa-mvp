"""DS-160 browser-extension helpers (W48 v0.2).

Three responsibilities:

1. **profile loading** — parse `Order.applicant_data` (JSON text) into a
   structured `ApplicantProfile` dict that matches the web-side contract
   (`frontend/web/src/composables/useApplicantProfile.js`).  Used by both
   the /code (server-side validation) and /redeem endpoints.

2. **fingerprinting** — `compute_fingerprint(profile)` returns the first
   32 hex chars of SHA-256 over a normalized snapshot of the DS-160
   fields.  The fingerprint is what makes the 12-digit code "versioned":
   any change to a tracked field → fingerprint avalanche → the old code
   is rejected on redeem with 409 ARCHIVE_CHANGED.

3. **code generation** — 12 base30 chars (Crockford-like, no 0/O/1/I/L/U),
   ~60 bits entropy via `secrets.choice`.

4. **in-memory rate limit** for /redeem (60s / 5 attempts per order+IP).
   Marked P1: production should swap in Redis (`app.core.config.redis_url`
   is already set for celery).

Design rationale lives in `browser-extension/DESIGN-v0.2.md`.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Optional

# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #

# 12-char base30, hand-picked to avoid 0/O/1/I/L/U visual confusion.
# 30^12 ≈ 5.3e17 (~60 bits entropy).
_DS160_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
_DS160_CODE_LEN = 12
_DS160_CODE_RE = re.compile(r"^[2-9A-HJ-NP-Z]{12}$")

# Fingerprint hex prefix length.  32 hex chars = 128 bits; ample collision
# resistance for a per-order archive-version tag.
_FINGERPRINT_HEX_LEN = 32

# Rate-limit thresholds (P1: swap to Redis when multi-worker).
_RATE_LIMIT_WINDOW_SEC = 60
_RATE_LIMIT_PER_ORDER = 5
_RATE_LIMIT_PER_IP = 10


# --------------------------------------------------------------------------- #
# ApplicantProfile — server-side mirror of useApplicantProfile.js             #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ApplicantProfile:
    """Subset of the web-side ApplicantProfile that we ship to the extension.

    Field names are kept identical to the JS contract so the extension can
    consume them without remapping.  Unknown / unmapped sections are
    tolerated — they're just ignored by the extension's fillEngine today.
    """
    identity: dict
    passport: dict
    contact: dict
    travel: dict
    previous: dict
    usContact: dict
    work: dict
    family: dict
    security: dict
    uk: dict
    au: dict

    def to_dict(self) -> dict:
        return {
            "identity": dict(self.identity),
            "passport": dict(self.passport),
            "contact": dict(self.contact),
            "travel": dict(self.travel),
            "previous": dict(self.previous),
            "usContact": dict(self.usContact),
            "work": dict(self.work),
            "family": dict(self.family),
            "security": dict(self.security),
            "uk": dict(self.uk),
            "au": dict(self.au),
        }


# --------------------------------------------------------------------------- #
# Profile loading                                                              #
# --------------------------------------------------------------------------- #

def _pick_raw(parsed: Mapping[str, Any], *keys: str) -> Any:
    """First non-empty value from flat applicant_data keys."""
    for key in keys:
        v = parsed.get(key)
        if v is None:
            continue
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v
        s = str(v).strip()
        if s:
            return v
    return ""


def _coerce_yes_no(raw: Any) -> Any:
    """Normalize wizard YES/NO strings to booleans for mapping valueMap."""
    if raw is True or raw is False:
        return raw
    if raw is None:
        return ""
    s = str(raw).strip().lower()
    if not s:
        return ""
    if s in ("true", "yes", "y", "1"):
        return True
    if s in ("false", "no", "n", "0"):
        return False
    return raw


def _nested_get(data: Mapping[str, Any], path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, Mapping):
            return ""
        cur = cur.get(part)
    return cur if cur is not None else ""


def _is_nested_profile(parsed: Mapping[str, Any]) -> bool:
    identity = parsed.get("identity")
    return isinstance(identity, Mapping) and (
        "givenName" in identity or "surname" in identity
    )


def _first_employment(parsed: Mapping[str, Any]) -> Mapping[str, Any]:
    jobs = parsed.get("employments")
    if isinstance(jobs, list) and jobs and isinstance(jobs[0], Mapping):
        return jobs[0]
    return {}


def _first_education(parsed: Mapping[str, Any]) -> Mapping[str, Any]:
    edus = parsed.get("educations")
    if isinstance(edus, list) and edus and isinstance(edus[0], Mapping):
        return edus[0]
    return {}


def _build_profile_from_flat(parsed: Mapping[str, Any]) -> ApplicantProfile:
    """Mirror `useApplicantProfile.buildApplicantProfile` — nested JS contract."""
    job = _first_employment(parsed)
    edu = _first_education(parsed)

    arrival = normalize_date(_pick_raw(parsed, "arrival_date"))
    stay_raw = _pick_raw(parsed, "stay_days")
    stay_length = ""
    if stay_raw != "":
        stay_length = f"{stay_raw} DAYS"

    has_plan_raw = _pick_raw(parsed, "has_plan")
    if has_plan_raw != "":
        has_plan = _coerce_yes_no(has_plan_raw)
    else:
        has_plan = bool(arrival)

    passport_type = _pick_raw(parsed, "passport_type", "passportType")
    if passport_type == "":
        passport_type = "regular"

    occupation = _pick_raw(parsed, "occupation") or _pick_raw(job, "occupation")
    has_education_raw = _pick_raw(parsed, "has_education")
    if has_education_raw != "":
        has_education = _coerce_yes_no(has_education_raw)
    else:
        has_education = bool(_pick_raw(edu, "school_name") or _pick_raw(parsed, "school_name"))

    emergency = parsed.get("emergency_contact")
    emergency_phone = ""
    if isinstance(emergency, Mapping):
        emergency_phone = str(emergency.get("phone") or "").strip()

    identity = {
        "surname": _pick_raw(parsed, "surname", "full_name"),
        "givenName": _pick_raw(parsed, "given_name", "givenName"),
        "nativeName": _pick_raw(parsed, "native_name", "nativeName"),
        "sex": _pick_raw(parsed, "sex", "gender"),
        "maritalStatus": _pick_raw(parsed, "marital_status", "maritalStatus"),
        "dob": normalize_date(_pick_raw(parsed, "birth_date", "dob")),
        "birthCity": _pick_raw(parsed, "birth_city", "birthCity"),
        "birthCountry": _pick_raw(parsed, "birth_country", "nationality"),
        "nationality": _pick_raw(parsed, "nationality"),
        "nationalId": _pick_raw(parsed, "national_id", "nationalId"),
        "hasOtherNationality": _coerce_yes_no(
            _pick_raw(parsed, "has_other_nationality", "hasOtherNationality")
        ),
        "usSsn": _pick_raw(parsed, "us_ssn", "usSsn"),
        "usTaxId": _pick_raw(parsed, "us_tax_id", "usTaxId"),
    }
    passport = {
        "type": passport_type,
        "number": _pick_raw(parsed, "passport_no", "passportNumber"),
        "bookNumber": _pick_raw(parsed, "passport_book_no", "passportBookNumber", "passport_book_number"),
        "issueCountry": _pick_raw(parsed, "passport_issue_country", "issueCountry", "nationality"),
        "issueCity": _pick_raw(parsed, "passport_issue_city", "issueCity"),
        "issueDate": normalize_date(_pick_raw(parsed, "passport_issue_date", "issueDate")),
        "expiry": normalize_date(_pick_raw(parsed, "passport_expiry", "passportExpiry")),
    }
    contact = {
        "street": _pick_raw(parsed, "home_street"),
        "city": _pick_raw(parsed, "home_city"),
        "state": _pick_raw(parsed, "home_state"),
        "postalCode": _pick_raw(parsed, "home_postal"),
        "country": _pick_raw(parsed, "home_country", "nationality"),
        "phone": _pick_raw(parsed, "phone") or emergency_phone,
        "email": _pick_raw(parsed, "email"),
    }
    travel = {
        "purpose": _pick_raw(parsed, "visa_type"),
        "hasPlan": has_plan,
        "arrivalDate": arrival,
        "departureDate": normalize_date(_pick_raw(parsed, "departure_date")),
        "stayLength": stay_length,
        "usAddress": _pick_raw(parsed, "hotel_name"),
        "payer": _pick_raw(parsed, "payer") or "self",
        "hasCompanions": _coerce_yes_no(_pick_raw(parsed, "has_companions")),
        "companion": {
            "surname": _pick_raw(parsed, "companion_surname"),
            "givenName": _pick_raw(parsed, "companion_given_name"),
            "relation": _pick_raw(parsed, "companion_relation"),
        },
    }
    previous = {
        "hasVisited": _coerce_yes_no(_pick_raw(parsed, "previous_has_visited")),
        "lastVisitDate": normalize_date(_pick_raw(parsed, "previous_last_visit_date")),
        "lastVisitStayDays": _pick_raw(parsed, "previous_last_visit_stay_days"),
        "hasVisa": _coerce_yes_no(_pick_raw(parsed, "previous_has_visa")),
        "lastVisaDate": normalize_date(_pick_raw(parsed, "previous_last_visa_date")),
        "lastVisaNumber": _pick_raw(parsed, "previous_last_visa_number"),
        "hasRefused": _coerce_yes_no(_pick_raw(parsed, "previous_has_refused")),
    }
    us_contact = {
        "personSurname": _pick_raw(parsed, "us_contact_surname"),
        "personGivenName": _pick_raw(parsed, "us_contact_given_name"),
        "orgName": _pick_raw(parsed, "us_contact_org"),
        "relation": _pick_raw(parsed, "us_contact_relation"),
        "street": _pick_raw(parsed, "us_contact_street"),
        "city": _pick_raw(parsed, "us_contact_city"),
        "state": _pick_raw(parsed, "us_contact_state"),
        "zip": _pick_raw(parsed, "us_contact_zip"),
        "phone": _pick_raw(parsed, "us_contact_phone"),
        "email": _pick_raw(parsed, "us_contact_email"),
    }
    work = {
        "occupation": occupation,
        "employer": _pick_raw(parsed, "employer_name") or _pick_raw(job, "employer_name"),
        "employerStreet": _pick_raw(parsed, "employer_street") or _pick_raw(job, "employer_address"),
        "employerCity": _pick_raw(parsed, "employer_city"),
        "employerState": _pick_raw(parsed, "employer_state"),
        "employerPostal": _pick_raw(parsed, "employer_postal"),
        "employerCountry": _pick_raw(parsed, "employer_country"),
        "employerPhone": _pick_raw(parsed, "employer_phone"),
        "monthlySalary": _pick_raw(parsed, "monthly_salary") or _pick_raw(job, "monthly_salary"),
        "duties": _pick_raw(parsed, "duties") or _pick_raw(job, "duties"),
        "hasEducation": has_education,
        "schoolName": _pick_raw(parsed, "school_name") or _pick_raw(edu, "school_name"),
        "courseOfStudy": _pick_raw(parsed, "course_of_study") or _pick_raw(edu, "course"),
        "schoolFrom": normalize_date(_pick_raw(parsed, "school_from") or _pick_raw(edu, "from")),
        "schoolTo": normalize_date(_pick_raw(parsed, "school_to") or _pick_raw(edu, "to")),
        "prevEmployer": _pick_raw(parsed, "prev_employer"),
    }
    family = {
        "spouse": {
            "surname": _pick_raw(parsed, "spouse_surname"),
            "givenName": _pick_raw(parsed, "spouse_given_name"),
            "dob": normalize_date(_pick_raw(parsed, "spouse_dob")),
            "nationality": _pick_raw(parsed, "spouse_nationality"),
        },
        "father": {
            "surname": _pick_raw(parsed, "father_surname"),
            "givenName": _pick_raw(parsed, "father_given_name"),
            "dob": normalize_date(_pick_raw(parsed, "father_dob")),
            "inUS": _coerce_yes_no(_pick_raw(parsed, "father_in_us")),
        },
        "mother": {
            "surname": _pick_raw(parsed, "mother_surname"),
            "givenName": _pick_raw(parsed, "mother_given_name"),
            "dob": normalize_date(_pick_raw(parsed, "mother_dob")),
            "inUS": _coerce_yes_no(_pick_raw(parsed, "mother_in_us")),
        },
        "hasUSRelatives": _coerce_yes_no(_pick_raw(parsed, "has_us_relatives")),
        "relative": {
            "surname": _pick_raw(parsed, "relative_surname"),
            "givenName": _pick_raw(parsed, "relative_given_name"),
            "relation": _pick_raw(parsed, "relative_relation"),
            "status": _pick_raw(parsed, "relative_status"),
        },
    }
    security = {
        "acknowledged": _coerce_yes_no(_pick_raw(parsed, "security_acknowledged")),
    }
    uk = {
        "visaLength": _pick_raw(parsed, "uk_visa_length") or "6_months",
        "mainReason": _pick_raw(parsed, "uk_main_reason", "visa_type") or "tourism",
        "fundsPayer": _pick_raw(parsed, "uk_funds_payer", "payer") or "self",
        "employmentStatus": _pick_raw(parsed, "uk_employment_status"),
        "employmentYears": _pick_raw(parsed, "uk_employment_years", "employment_years"),
        "fundsBalanceBucket": _pick_raw(parsed, "uk_funds_balance_bucket", "funds_balance_bucket"),
        "visaHistory": _pick_raw(parsed, "uk_visa_history"),
        "ukVisaRefused": _coerce_yes_no(_pick_raw(parsed, "uk_visa_refused")),
        "otherVisaRefused": _coerce_yes_no(_pick_raw(parsed, "uk_other_visa_refused")),
    }
    au = {
        "stream": _pick_raw(parsed, "au_stream") or "tourist",
        "reasonForVisit": _pick_raw(parsed, "au_reason_for_visit", "visa_type") or "tourism",
        "employmentStatus": _pick_raw(parsed, "au_employment_status"),
        "employmentYears": _pick_raw(parsed, "au_employment_years", "employment_years"),
        "fundsBalanceBucket": _pick_raw(parsed, "au_funds_balance_bucket", "funds_balance_bucket"),
        "developedCountryVisa": _pick_raw(parsed, "au_developed_country_visa", "developed_country_visa"),
        "auVisaRefused": _coerce_yes_no(_pick_raw(parsed, "au_visa_refused")),
    }
    return ApplicantProfile(
        identity=identity,
        passport=passport,
        contact=contact,
        travel=travel,
        previous=previous,
        usContact=us_contact,
        work=work,
        family=family,
        security=security,
        uk=uk,
        au=au,
    )


def _normalize_nested_profile(parsed: Mapping[str, Any]) -> ApplicantProfile:
    """Accept profile already in nested ApplicantProfile shape (redeem round-trip)."""
    def sub(section: str, defaults: Mapping[str, Any]) -> dict:
        raw = parsed.get(section)
        if not isinstance(raw, Mapping):
            return dict(defaults)
        out = dict(defaults)
        for key, default in defaults.items():
            if isinstance(default, Mapping):
                nested = raw.get(key)
                if isinstance(nested, Mapping):
                    out[key] = {**default, **{k: nested.get(k, "") for k in default}}
                else:
                    out[key] = dict(default)
            else:
                val = raw.get(key, "")
                if key in ("dob", "issueDate", "expiry", "arrivalDate", "schoolFrom", "schoolTo",
                           "lastVisitDate", "lastVisaDate"):
                    out[key] = normalize_date(val) if val else ""
                elif key in ("hasOtherNationality", "hasPlan", "hasCompanions", "hasVisited",
                             "hasVisa", "hasRefused", "hasEducation", "hasUSRelatives",
                             "acknowledged", "inUS"):
                    out[key] = _coerce_yes_no(val) if val != "" else ""
                else:
                    out[key] = val if val is not None else ""
        return out

    return ApplicantProfile(
        identity=sub("identity", {
            "surname": "", "givenName": "", "nativeName": "", "sex": "", "maritalStatus": "",
            "dob": "", "birthCity": "", "birthCountry": "", "nationality": "", "nationalId": "",
            "hasOtherNationality": "", "usSsn": "", "usTaxId": "",
        }),
        passport=sub("passport", {
            "type": "regular", "number": "", "bookNumber": "", "issueCountry": "",
            "issueCity": "", "issueDate": "", "expiry": "",
        }),
        contact=sub("contact", {
            "street": "", "city": "", "state": "", "postalCode": "", "country": "",
            "phone": "", "email": "",
        }),
        travel=sub("travel", {
            "purpose": "", "hasPlan": "", "arrivalDate": "", "departureDate": "", "stayLength": "",
            "usAddress": "", "payer": "self", "hasCompanions": "",
            "companion": {"surname": "", "givenName": "", "relation": ""},
        }),
        previous=sub("previous", {
            "hasVisited": "", "lastVisitDate": "", "lastVisitStayDays": "",
            "hasVisa": "", "lastVisaDate": "", "lastVisaNumber": "", "hasRefused": "",
        }),
        usContact=sub("usContact", {
            "personSurname": "", "personGivenName": "", "orgName": "", "relation": "",
            "street": "", "city": "", "state": "", "zip": "", "phone": "", "email": "",
        }),
        work=sub("work", {
            "occupation": "", "employer": "", "employerStreet": "", "employerCity": "",
            "employerState": "", "employerPostal": "", "employerCountry": "", "employerPhone": "",
            "monthlySalary": "", "duties": "", "hasEducation": "", "schoolName": "",
            "courseOfStudy": "", "schoolFrom": "", "schoolTo": "", "prevEmployer": "",
        }),
        family=sub("family", {
            "spouse": {"surname": "", "givenName": "", "dob": "", "nationality": ""},
            "father": {"surname": "", "givenName": "", "dob": "", "inUS": ""},
            "mother": {"surname": "", "givenName": "", "dob": "", "inUS": ""},
            "hasUSRelatives": "",
            "relative": {"surname": "", "givenName": "", "relation": "", "status": ""},
        }),
        security=sub("security", {"acknowledged": ""}),
        uk=sub("uk", {
            "visaLength": "6_months", "mainReason": "tourism", "fundsPayer": "self",
            "employmentStatus": "", "employmentYears": "", "fundsBalanceBucket": "",
            "visaHistory": "", "ukVisaRefused": "", "otherVisaRefused": "",
        }),
        au=sub("au", {
            "stream": "tourist", "reasonForVisit": "tourism", "employmentStatus": "",
            "employmentYears": "", "fundsBalanceBucket": "", "developedCountryVisa": "",
            "auVisaRefused": "",
        }),
    )


def load_applicant_profile(applicant_data_raw: Optional[str]) -> ApplicantProfile:
    """Parse `Order.applicant_data` (JSON text) into an ApplicantProfile.

    Output matches `useApplicantProfile.js` nested contract so
    `ds160FieldMap.js` profile paths resolve correctly in the plugin.
    """
    parsed: dict = {}
    if applicant_data_raw:
        try:
            parsed = json.loads(applicant_data_raw)
        except (ValueError, TypeError):
            parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    if _is_nested_profile(parsed):
        return _normalize_nested_profile(parsed)
    return _build_profile_from_flat(parsed)


# --------------------------------------------------------------------------- #
# Date normalization (mirror of useApplicantProfile.normalizeDate)              #
# --------------------------------------------------------------------------- #

_MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
           "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def normalize_date(raw: Any) -> str:
    """Coerce various date string shapes → ISO 'YYYY-MM-DD'.  Returns '' if unparseable."""
    if not raw:
        return ""
    s = str(raw).strip().upper()
    if not s:
        return ""

    # YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", s)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"

    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY (Vietnamese / Indonesian style)
    m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", s)
    if m:
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"

    # DD MMM YYYY or DD-MMM-YYYY (passport MRZ style)
    m = re.match(r"^(\d{1,2})[-\s]([A-Z]{3})[-\s](\d{4})$", s)
    if m and m[2] in _MONTHS:
        d, mo, y = int(m[1]), _MONTHS[m[2]], int(m[3])
        return f"{y:04d}-{mo:02d}-{d:02d}"

    return ""  # unparseable → empty (don't fake it)


# --------------------------------------------------------------------------- #
# Fingerprint                                                                  #
# --------------------------------------------------------------------------- #

# Fields that participate in the fingerprint (dot paths, nested ApplicantProfile).
_FP_FIELDS: list[str] = [
    "identity.surname",
    "identity.givenName",
    "identity.nativeName",
    "identity.sex",
    "identity.maritalStatus",
    "identity.dob",
    "identity.birthCity",
    "identity.birthCountry",
    "identity.nationality",
    "identity.nationalId",
    "identity.hasOtherNationality",
    "passport.type",
    "passport.number",
    "passport.bookNumber",
    "passport.issueCountry",
    "passport.issueCity",
    "passport.issueDate",
    "passport.expiry",
    "contact.street",
    "contact.city",
    "contact.state",
    "contact.postalCode",
    "contact.country",
    "contact.phone",
    "contact.email",
    "travel.purpose",
    "travel.hasPlan",
    "travel.arrivalDate",
    "travel.stayLength",
    "travel.usAddress",
    "travel.payer",
    "travel.hasCompanions",
    "travel.companion.surname",
    "travel.companion.givenName",
    "travel.companion.relation",
    "previous.hasVisited",
    "previous.lastVisitDate",
    "previous.lastVisitStayDays",
    "previous.hasVisa",
    "previous.lastVisaDate",
    "previous.lastVisaNumber",
    "previous.hasRefused",
    "usContact.personSurname",
    "usContact.personGivenName",
    "usContact.orgName",
    "usContact.relation",
    "usContact.street",
    "usContact.city",
    "usContact.state",
    "usContact.zip",
    "usContact.phone",
    "usContact.email",
    "work.occupation",
    "work.employer",
    "work.employerStreet",
    "work.employerCity",
    "work.employerState",
    "work.employerPostal",
    "work.employerCountry",
    "work.employerPhone",
    "work.monthlySalary",
    "work.duties",
    "work.hasEducation",
    "work.schoolName",
    "work.courseOfStudy",
    "work.schoolFrom",
    "work.schoolTo",
    "work.prevEmployer",
    "family.spouse.surname",
    "family.spouse.givenName",
    "family.spouse.dob",
    "family.spouse.nationality",
    "family.father.surname",
    "family.father.givenName",
    "family.father.dob",
    "family.father.inUS",
    "family.mother.surname",
    "family.mother.givenName",
    "family.mother.dob",
    "family.mother.inUS",
    "family.hasUSRelatives",
    "family.relative.surname",
    "family.relative.givenName",
    "family.relative.relation",
    "family.relative.status",
]

_FP_DATE_PATHS = frozenset({
    "identity.dob",
    "passport.issueDate",
    "passport.expiry",
    "travel.arrivalDate",
    "previous.lastVisitDate",
    "previous.lastVisaDate",
    "work.schoolFrom",
    "work.schoolTo",
    "family.spouse.dob",
    "family.father.dob",
    "family.mother.dob",
})


def _normalize_value(v: Any) -> str:
    """Stable string representation for fingerprint hashing.

    Whitespace and case are noise on the form; treating them as significant
    would generate spurious fingerprints when a user re-saves a value.
    Booleans, dates, and None all collapse to deterministic strings.
    """
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (date, datetime)):
        # ISO 8601, date only for date objects
        if isinstance(v, datetime):
            return v.date().isoformat()
        return v.isoformat()
    if isinstance(v, (int, float)):
        return str(v)
    return str(v).strip().lower()


def compute_fingerprint(
    profile: ApplicantProfile | Mapping[str, Mapping[str, Any]],
    extra_salt: str = "",
) -> str:
    """SHA-256 hex (32 chars) of the normalized fingerprint snapshot.

    Any tracked-field change → output diverges (avalanche property of SHA-256).
    Whitespace + case + type differences in the *non-tracked* fields are
    irrelevant; we only walk `_FP_FIELDS`.

    `extra_salt` is an opaque string mixed into the hash.  The /code endpoint
    uses it on force_rotate to guarantee the fingerprint changes — without a
    per-order revoked-codes list, this is how old codes get invalidated.
    """
    flat: dict[str, str] = {}
    sections = profile.to_dict() if isinstance(profile, ApplicantProfile) else dict(profile)
    for path in _FP_FIELDS:
        raw = _nested_get(sections, path)
        if path in _FP_DATE_PATHS:
            flat[path] = _normalize_value(normalize_date(raw))
        else:
            flat[path] = _normalize_value(raw)
    if extra_salt:
        flat["__salt__"] = _normalize_value(extra_salt)

    payload = json.dumps(flat, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:_FINGERPRINT_HEX_LEN]


def has_minimum_fields(profile: ApplicantProfile) -> bool:
    """Heuristic: enough data to make a DS-160 attempt worthwhile.

    We require at minimum: name, dob, nationality, passport number.  Without
    these the form can't meaningfully start; the wizard should prompt the
    user to fill these before a code is even requested.
    """
    ident = profile.identity
    pp = profile.passport
    return all([
        ident.get("surname"),
        ident.get("givenName"),
        ident.get("dob"),
        ident.get("nationality"),
        pp.get("number"),
    ])


# --------------------------------------------------------------------------- #
# Code generation & validation                                                  #
# --------------------------------------------------------------------------- #

def generate_code() -> str:
    """Cryptographically random 12-char base30 string."""
    return "".join(secrets.choice(_DS160_ALPHABET) for _ in range(_DS160_CODE_LEN))


def hash_code(code: str) -> str:
    """SHA-256 hex of a normalized DS-160 code (never store plaintext)."""
    normalized = normalize_code_input(code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def code_log_prefix(code_or_hash: str) -> str:
    """Safe log fragment: first 8 chars of the hash (never the raw code)."""
    if not code_or_hash:
        return ""
    if len(code_or_hash) == 64 and all(c in "0123456789abcdef" for c in code_or_hash.lower()):
        return code_or_hash[:8]
    return hash_code(code_or_hash)[:8]


def normalize_code_input(raw: str) -> str:
    """User-friendly: strip dashes/spaces, uppercase, validate charset."""
    if not raw:
        return ""
    s = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    return s


def is_valid_code_format(code: str) -> bool:
    return bool(code and _DS160_CODE_RE.match(code))


# Plugin authorization TTL — short window reduces leak blast radius (E-04).
DS160_CODE_TTL_SECONDS = 10 * 60


def revoke_order_ds160(order: Any) -> bool:
    """Invalidate plugin authorization on an Order ORM row. Returns True if changed.

    Used by refund / cancel / disable paths (C-05). Accepts any object with the
    ds160_* attributes to avoid circular imports with the API layer.
    """
    changed = False
    code_hash = getattr(order, "ds160_code_hash", None)
    revoked_raw = getattr(order, "ds160_revoked_codes", None)
    revoked: list = []
    if revoked_raw:
        try:
            parsed = json.loads(revoked_raw)
            if isinstance(parsed, list):
                revoked = parsed
        except (ValueError, TypeError):
            revoked = []
    if code_hash and not getattr(order, "ds160_code_revoked", False):
        if code_hash not in revoked:
            revoked.append(code_hash)
        order.ds160_revoked_codes = json.dumps(revoked[-50:], ensure_ascii=False)
        order.ds160_code_revoked = True
        changed = True
    elif code_hash and code_hash not in revoked:
        revoked.append(code_hash)
        order.ds160_revoked_codes = json.dumps(revoked[-50:], ensure_ascii=False)
        order.ds160_code_revoked = True
        changed = True
    if getattr(order, "ds160_code", None) is not None:
        order.ds160_code = None
        changed = True
    return changed


# --------------------------------------------------------------------------- #
# In-memory rate limit (P1: swap to Redis)                                    #
# --------------------------------------------------------------------------- #

@dataclass
class _Bucket:
    """Sliding-window-ish counter.  Reset on first hit after window expiry."""
    window_start: float
    count: int


class InMemoryRateLimiter:
    """Thread-safe per-key sliding-window counter.

    For DS-160 /redeem: 60-second window, default 5/order and 10/IP.
    Production (multi-worker / multi-pod) must replace this with Redis
    INCR + EXPIRE — see `app.core.config.redis_url`.  Tests can construct
    one and reset via `_buckets.clear()` for isolation.
    """

    def __init__(
        self,
        window_sec: int = _RATE_LIMIT_WINDOW_SEC,
        per_key_limits: Optional[dict[str, int]] = None,
    ) -> None:
        self.window_sec = window_sec
        self.limits = per_key_limits or {
            "order": _RATE_LIMIT_PER_ORDER,
            "ip": _RATE_LIMIT_PER_IP,
        }
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def check_and_hit(self, keys: dict[str, str]) -> tuple[bool, str]:
        """Atomically increment counters for each (kind, value) pair.

        Returns (allowed, error_code).  When denied, error_code is 'RATE_LIMITED'.
        """
        now = time.monotonic()
        with self._lock:
            for kind, value in keys.items():
                limit = self.limits.get(kind)
                if limit is None:
                    continue
                key = f"{kind}:{value}"
                bucket = self._buckets.get(key)
                if bucket is None or now - bucket.window_start >= self.window_sec:
                    self._buckets[key] = _Bucket(window_start=now, count=1)
                    continue
                if bucket.count >= limit:
                    return False, "RATE_LIMITED"
                bucket.count += 1
        return True, ""

    def reset(self) -> None:
        """For tests only."""
        with self._lock:
            self._buckets.clear()


# Module-level default instance — endpoints reuse this.  Tests should use a
# fresh limiter (passed via dependency override).
_default_limiter = InMemoryRateLimiter()


def get_default_rate_limiter() -> InMemoryRateLimiter:
    return _default_limiter