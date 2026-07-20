"""Product destination allowlist — single source of truth.

Customer market (who we sell to): Vietnam / Indonesia passport holders.
Visa destinations (what we file): US / GB / AU / Schengen only.

See docs/PRODUCT_SCOPE.md.
"""
from __future__ import annotations

# National (non-Schengen) product lines
PRODUCT_NATIONAL_CODES: frozenset[str] = frozenset({"US", "GB", "UK", "AU"})

# Schengen representatives surfaced on apply/diagnose cards.
# Full 26-member picker lives on /schengen (any member can issue the visa).
PRODUCT_SCHENGEN_CODES: frozenset[str] = frozenset({"DE", "FR"})

# All destination codes selectable on primary product surfaces
# (home / apply / diagnose / destinations list).
PRODUCT_DESTINATION_CODES: frozenset[str] = (
    PRODUCT_NATIONAL_CODES | PRODUCT_SCHENGEN_CODES
)

# Full Schengen area — allowed for diagnose / wizard when user picks via /schengen
SCHENGEN_MEMBER_CODES: frozenset[str] = frozenset({
    "AT", "BE", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IS", "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO",
    "PL", "PT", "SK", "SI", "ES", "SE", "CH",
})

# Anything a public client may submit as destination (product + full Schengen)
ALLOWED_DESTINATION_CODES: frozenset[str] = (
    PRODUCT_NATIONAL_CODES | SCHENGEN_MEMBER_CODES
)

# Legacy / non-product destination codes that must never be offered or filed
NON_PRODUCT_DESTINATION_CODES: frozenset[str] = frozenset({
    "ID", "VN", "JP", "CA", "SG", "NZ", "KR", "TH", "PH", "MY",
})


def normalize_destination_code(code: str | None) -> str:
    cc = (code or "").strip().upper()
    if cc == "UK":
        return "GB"
    return cc


def is_allowed_destination(code: str | None) -> bool:
    return normalize_destination_code(code) in ALLOWED_DESTINATION_CODES


def is_product_card_destination(code: str | None) -> bool:
    """True for the short list shown on apply/diagnose/home cards."""
    return normalize_destination_code(code) in {
        normalize_destination_code(c) for c in PRODUCT_DESTINATION_CODES
    }
