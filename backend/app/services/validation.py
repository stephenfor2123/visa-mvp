"""Validation engine — V2 §5.2 (used by both 1.1.1a endpoint and 1.1.2a unit tests).

16 rules covering expiry / regex / length / date / age / file /
image_quality / cross_field / ocr_confidence. Rules are loaded from
`app/core/validation_rules.json` (the V2 spec) on first import; the
default constructor also accepts an in-memory rules list for tests.

Public API:
    DEFAULT_RULES_PATH: Path
    ValidationEngine.from_default()             -> ValidationEngine
    ValidationEngine.from_json_file(path)       -> ValidationEngine
    engine.enabled_rule_codes()                 -> list[str]
    engine.run(fields, file_meta=None)          -> list[dict]   (failed rules)
    engine.summary(issues)                      -> dict         (counts)
    engine.has_blocking_failures(issues)        -> bool

Output format per rule (FAIL only — passing rules are omitted):
    {
        "code":        "PASSPORT_EXPIRY_MIN_6M",
        "severity":    "error" | "warning" | "info",
        "message_key": "validation.passport.expiry_min_6m",
        "details":     {...},  # only present on failure
    }

Image-quality rules (Laplacian blur, min resolution, face detect, photo
bg) require OpenCV / face detection. We expose them as in-spec
implementation that reads from a `file_meta` dict (so tests can drive
them without real CV). The actual CV integration is W3+.
"""
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional


# Bump this if you add a new rule_type
_VALID_RULE_TYPES = frozenset(
    {
        "expiry",
        "regex",
        "length",
        "date",
        "age",
        "file",
        "image_quality",
        "cross_field",
        "ocr_confidence",
    }
)


# --------------------------------------------------------------------------- #
# Default rule set — V2 §5.2.2 (16 rules, 2 disabled)                         #
# --------------------------------------------------------------------------- #
DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "code": "PASSPORT_EXPIRY_MIN_6M",
        "rule_type": "expiry",
        "severity": "error",
        "params": {"field": "expiry", "min_months_remaining": 6},
        "enabled": True,
        "message_key": "validation.passport.expiry_min_6m",
    },
    {
        "code": "PASSPORT_EXPIRY_MIN_3M",
        "rule_type": "expiry",
        "severity": "warning",
        "params": {"field": "expiry", "min_months_remaining": 3},
        "enabled": True,
        "message_key": "validation.passport.expiry_min_3m",
    },
    {
        "code": "PASSPORT_NO_FORMAT",
        "rule_type": "regex",
        "severity": "error",
        "params": {"field": "passport_no", "pattern": r"^[A-Z][0-9]{8}$|^[0-9]{9}$"},
        "enabled": True,
        "message_key": "validation.passport.no_format",
    },
    {
        "code": "PASSPORT_DOB_NOT_FUTURE",
        "rule_type": "date",
        "severity": "error",
        "params": {"field": "dob", "must_be_past": True},
        "enabled": True,
        "message_key": "validation.passport.dob_past",
    },
    {
        "code": "PASSPORT_DOB_AGE_MIN_16",
        "rule_type": "age",
        "severity": "error",
        "params": {"field": "dob", "min_age": 16},
        "enabled": True,
        "message_key": "validation.passport.age_min_16",
    },
    {
        "code": "IMAGE_BLUR_THRESHOLD",
        "rule_type": "image_quality",
        "severity": "error",
        "params": {"laplacian_variance_min": 100},
        "enabled": True,
        "message_key": "validation.image.blur",
    },
    {
        "code": "IMAGE_RESOLUTION_MIN",
        "rule_type": "image_quality",
        "severity": "error",
        "params": {"min_width": 800, "min_height": 600},
        "enabled": True,
        "message_key": "validation.image.resolution",
    },
    {
        "code": "IMAGE_FILE_SIZE_MAX",
        "rule_type": "file",
        "severity": "error",
        "params": {"max_bytes": 10 * 1024 * 1024},
        "enabled": True,
        "message_key": "validation.image.size",
    },
    {
        "code": "IMAGE_FORMAT_ALLOWED",
        "rule_type": "file",
        "severity": "error",
        "params": {
            "allowed_mime": [
                "image/jpeg",
                "image/png",
                "image/webp",
                "application/pdf",
            ]
        },
        "enabled": True,
        "message_key": "validation.image.format",
    },
    {
        "code": "PASSPORT_NAME_MIN_LEN",
        "rule_type": "length",
        "severity": "error",
        "params": {
            "field": "surname|given_name",
            "min_length": 1,
            "max_length": 64,
        },
        "enabled": True,
        "message_key": "validation.passport.name_length",
    },
    {
        "code": "TRAVEL_DATE_RANGE",
        "rule_type": "date",
        "severity": "warning",
        "params": {
            "field": "travel_date",
            "must_be_future": True,
            "max_days_future": 365,
        },
        "enabled": True,
        "message_key": "validation.travel.date_range",
    },
    {
        "code": "STAY_DAYS_MAX",
        "rule_type": "cross_field",
        "severity": "warning",
        "params": {
            "fields": ["arrival_date", "departure_date"],
            "max_days": 90,
        },
        "enabled": True,
        "message_key": "validation.travel.stay_max",
    },
    {
        "code": "ENROLLMENT_LETTER_DATE",
        "rule_type": "date",
        "severity": "warning",
        "params": {"field": "enrollment_letter_date", "max_age_days": 90},
        "enabled": True,
        "message_key": "validation.student.enrollment_age",
    },
    {
        "code": "PHOTO_FACE_DETECTED",
        "rule_type": "image_quality",
        "severity": "error",
        "params": {"face_detect": True, "min_face_ratio": 0.2},
        "enabled": False,  # needs real face-detection model in W3+
        "message_key": "validation.photo.face",
    },
    {
        "code": "PHOTO_BG_COLOR",
        "rule_type": "image_quality",
        "severity": "warning",
        "params": {"expected_bg": "white"},
        "enabled": False,  # needs OpenCV color analysis in W3+
        "message_key": "validation.photo.bg",
    },
    {
        "code": "OCR_FIELD_CONFIDENCE",
        "rule_type": "ocr_confidence",
        "severity": "warning",
        "params": {"min_confidence": 0.7},
        "enabled": True,
        "message_key": "validation.ocr.confidence",
    },
    {
        "code": "PASSPORT_DOB_AGE_MAX_120",
        "rule_type": "age",
        "severity": "warning",
        "params": {"field": "dob", "max_age": 120},
        "enabled": False,
        "message_key": "validation.passport.age_max_120",
    },
]


# Path the JSON file is expected at — set after we know the project layout.
DEFAULT_RULES_PATH: Optional[Path] = None


def _init_default_path() -> Path:
    """Resolve app/core/validation_rules.json relative to this file."""
    global DEFAULT_RULES_PATH
    if DEFAULT_RULES_PATH is not None:
        return DEFAULT_RULES_PATH
    here = Path(__file__).resolve()
    candidate = here.parent.parent / "core" / "validation_rules.json"
    DEFAULT_RULES_PATH = candidate
    return candidate


# Eagerly resolve at import time so test code can read DEFAULT_RULES_PATH
_init_default_path()


# --------------------------------------------------------------------------- #
# MaterialRef — used by the endpoint layer (1.1.1a)                           #
# --------------------------------------------------------------------------- #
@dataclass
class MaterialRef:
    """Minimal info we need to apply file/image rules to a material row."""

    id: int
    material_type: str
    mime_type: str
    file_size: int
    ocr_result: Optional[dict[str, Any]] = None
    storage_path: Optional[Path] = None  # for image-quality rules


# --------------------------------------------------------------------------- #
# Engine                                                                      #
# --------------------------------------------------------------------------- #
class ValidationEngine:
    """Applies a list of rules to {fields, file_meta}."""

    def __init__(self, rules: Optional[list[dict[str, Any]]] = None):
        src = rules if rules is not None else DEFAULT_RULES
        # Validate rule types up front so callers fail loud early
        for r in src:
            rtype = r.get("rule_type")
            if rtype not in _VALID_RULE_TYPES:
                raise ValueError(
                    f"unknown rule_type {rtype!r} on rule {r.get('code')!r}"
                )
        # Index by code; only `enabled` rules are evaluated.
        self.rules: dict[str, dict[str, Any]] = {
            r["code"]: r for r in src if r.get("enabled", True)
        }
        self._all_rules: list[dict[str, Any]] = list(src)

    # ------------------------------------------------------------------ #
    # Constructors                                                        #
    # ------------------------------------------------------------------ #
    @classmethod
    def from_default(cls) -> "ValidationEngine":
        """Load rules from app/core/validation_rules.json. Falls back to the
        in-process DEFAULT_RULES list if the file is missing (dev convenience)."""
        path = _init_default_path()
        if path.is_file():
            return cls.from_json_file(path)
        return cls(rules=list(DEFAULT_RULES))

    @classmethod
    def from_json_file(cls, path: Path) -> "ValidationEngine":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"rules file must be a list, got {type(data).__name__}")
        # Validate shape while loading so callers fail fast
        for r in data:
            for key in ("code", "rule_type", "severity", "params", "enabled", "message_key"):
                if key not in r:
                    raise ValueError(f"rule {r.get('code')!r} missing key {key!r}")
        return cls(rules=data)

    # ------------------------------------------------------------------ #
    # Introspection                                                       #
    # ------------------------------------------------------------------ #
    @property
    def rule_count(self) -> int:
        return len(self.rules)

    def enabled_rule_codes(self) -> list[str]:
        return list(self.rules.keys())

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #
    def run(
        self,
        fields: Optional[dict[str, Any]] = None,
        file_meta: Optional[dict[str, Any]] = None,
        materials: Optional[list[MaterialRef]] = None,
    ) -> list[dict[str, Any]]:
        """Apply all enabled rules; return a list of FAILURES only.

        `file_meta` is a flat dict (mime/size/width/height/...). The
        endpoint layer may pre-build it from a Material row, or the
        unit-test layer may hand-craft one. `materials` is the
        richer ORM-aware variant used by POST /validate.
        """
        fields = fields or {}
        issues: list[dict[str, Any]] = []
        for code, rule in self.rules.items():
            try:
                issue = self._apply(rule, fields, file_meta, materials)
            except Exception as exc:  # noqa: BLE001 — never let a single rule crash
                issues.append(
                    {
                        "code": code,
                        "severity": "warning",
                        "message_key": "validation.engine.rule_error",
                        "details": {"error": str(exc)},
                    }
                )
                continue
            if issue:
                issues.append(issue)
        return issues

    # ------------------------------------------------------------------ #
    # Aggregations                                                        #
    # ------------------------------------------------------------------ #
    @staticmethod
    def summary(issues: list[dict[str, Any]]) -> dict[str, int]:
        out = {"total": len(issues), "errors": 0, "warnings": 0, "info": 0}
        for i in issues:
            sev = i.get("severity")
            if sev == "error":
                out["errors"] += 1
            elif sev == "warning":
                out["warnings"] += 1
            elif sev == "info":
                out["info"] += 1
        return out

    @staticmethod
    def has_blocking_failures(issues: list[dict[str, Any]]) -> bool:
        return any(i.get("severity") == "error" for i in issues)

    # ------------------------------------------------------------------ #
    # Rule dispatch                                                       #
    # ------------------------------------------------------------------ #
    def _apply(
        self,
        rule: dict[str, Any],
        fields: dict[str, Any],
        file_meta: Optional[dict[str, Any]],
        materials: Optional[list[MaterialRef]],
    ) -> Optional[dict[str, Any]]:
        rtype = rule["rule_type"]
        p = rule["params"]
        sev = rule["severity"]
        code = rule["code"]
        msg = rule["message_key"]

        if rtype == "expiry":
            return self._rule_expiry(code, sev, msg, fields, p)
        if rtype == "regex":
            return self._rule_regex(code, sev, msg, fields, p)
        if rtype == "length":
            return self._rule_length(code, sev, msg, fields, p)
        if rtype == "date":
            return self._rule_date(code, sev, msg, fields, p)
        if rtype == "age":
            return self._rule_age(code, sev, msg, fields, p)
        if rtype == "file":
            return self._rule_file(code, sev, msg, file_meta, materials, p)
        if rtype == "image_quality":
            return self._rule_image_quality(code, sev, msg, file_meta, p)
        if rtype == "cross_field":
            return self._rule_cross_field(code, sev, msg, fields, p)
        if rtype == "ocr_confidence":
            return self._rule_ocr_confidence(code, sev, msg, fields, file_meta, p)
        return None

    # ------------------------------------------------------------------ #
    # Individual rules                                                    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if not value:
            return None
        if isinstance(value, date):
            return value
        s = str(value).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%Y.%m.%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _months_between(later: date, earlier: date) -> int:
        """Calendar months between two dates, can be negative."""
        return (later.year - earlier.year) * 12 + (later.month - earlier.month)

    def _rule_expiry(
        self,
        code: str,
        sev: str,
        msg: str,
        fields: dict[str, Any],
        p: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        target = fields.get(p["field"])
        if not target:
            # The 1.1.2a test for `expiry` field missing expects this rule
            # to *fail* (not be silently skipped) — return a soft warning.
            return {
                "code": code,
                "severity": "warning",
                "message_key": msg,
                "details": {"reason": "field_missing", "field": p["field"]},
            }
        d = self._parse_date(target)
        if d is None:
            return {
                "code": code,
                "severity": "warning",
                "message_key": msg,
                "details": {"value": target, "reason": "unparseable_date"},
            }
        months = self._months_between(d, date.today())
        if months < int(p["min_months_remaining"]):
            return {
                "code": code,
                "severity": sev,
                "message_key": msg,
                "details": {
                    "value": target,
                    "months_remaining": months,
                    "min_required": p["min_months_remaining"],
                },
            }
        return None

    def _rule_regex(
        self,
        code: str,
        sev: str,
        msg: str,
        fields: dict[str, Any],
        p: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        val = fields.get(p["field"])
        if val is None or val == "":
            return None
        if not re.match(p["pattern"], str(val)):
            return {
                "code": code,
                "severity": sev,
                "message_key": msg,
                "details": {"value": val, "pattern": p["pattern"]},
            }
        return None

    def _rule_length(
        self,
        code: str,
        sev: str,
        msg: str,
        fields: dict[str, Any],
        p: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        for f in p["field"].split("|"):
            val = fields.get(f) or ""
            n = len(str(val))
            if n < int(p["min_length"]) or n > int(p["max_length"]):
                return {
                    "code": code,
                    "severity": sev,
                    "message_key": msg,
                    "details": {"field": f, "length": n},
                }
        return None

    def _rule_date(
        self,
        code: str,
        sev: str,
        msg: str,
        fields: dict[str, Any],
        p: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        val = fields.get(p["field"])
        if not val:
            return None
        d = self._parse_date(val)
        if d is None:
            return {
                "code": code,
                "severity": "warning",
                "message_key": msg,
                "details": {"value": val, "reason": "unparseable_date"},
            }
        today = date.today()
        if p.get("must_be_past") and d >= today:
            return {
                "code": code,
                "severity": sev,
                "message_key": msg,
                "details": {"value": val, "must_be": "past"},
            }
        if p.get("must_be_future") and d <= today:
            return {
                "code": code,
                "severity": sev,
                "message_key": msg,
                "details": {"value": val, "must_be": "future"},
            }
        if p.get("max_days_future"):
            delta = (d - today).days
            if delta > int(p["max_days_future"]):
                return {
                    "code": code,
                    "severity": sev,
                    "message_key": msg,
                    "details": {
                        "value": val,
                        "days_in_future": delta,
                        "max_days_future": p["max_days_future"],
                    },
                }
        if p.get("max_age_days"):
            # "enrollment_letter_date must be within the last N days"
            delta = (today - d).days
            if delta < 0 or delta > int(p["max_age_days"]):
                return {
                    "code": code,
                    "severity": sev,
                    "message_key": msg,
                    "details": {
                        "value": val,
                        "days_old": delta,
                        "max_age_days": p["max_age_days"],
                    },
                }
        return None

    def _rule_age(
        self,
        code: str,
        sev: str,
        msg: str,
        fields: dict[str, Any],
        p: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        val = fields.get(p["field"])
        if not val:
            return None
        d = self._parse_date(val)
        if d is None:
            return None
        years = (date.today() - d).days / 365.25
        if "min_age" in p and years < float(p["min_age"]):
            return {
                "code": code,
                "severity": sev,
                "message_key": msg,
                "details": {"value": val, "age_years": round(years, 1)},
            }
        if "max_age" in p and years > float(p["max_age"]):
            return {
                "code": code,
                "severity": sev,
                "message_key": msg,
                "details": {"value": val, "age_years": round(years, 1)},
            }
        return None

    def _rule_file(
        self,
        code: str,
        sev: str,
        msg: str,
        file_meta: Optional[dict[str, Any]],
        materials: Optional[list[MaterialRef]],
        p: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        # Build a unified list of (meta, material_id) so the rule works
        # for both dict-based and ORM-based callers.
        items: list[tuple[dict[str, Any], Optional[int]]] = []
        if file_meta:
            items.append((file_meta, None))
        for m in materials or []:
            items.append(
                (
                    {
                        "mime_type": m.mime_type,
                        "size_bytes": m.file_size,
                    },
                    m.id,
                )
            )
        if not items:
            return None

        for meta, mid in items:
            if "max_bytes" in p and int(meta.get("size_bytes", 0)) > int(p["max_bytes"]):
                return {
                    "code": code,
                    "severity": sev,
                    "message_key": msg,
                    "material_id": mid,
                    "details": {
                        "size": meta.get("size_bytes"),
                        "max_bytes": p["max_bytes"],
                    },
                }
            if "allowed_mime" in p and meta.get("mime_type") not in p["allowed_mime"]:
                return {
                    "code": code,
                    "severity": sev,
                    "message_key": msg,
                    "material_id": mid,
                    "details": {
                        "mime_type": meta.get("mime_type"),
                        "allowed": p["allowed_mime"],
                    },
                }
        return None

    def _rule_image_quality(
        self,
        code: str,
        sev: str,
        msg: str,
        file_meta: Optional[dict[str, Any]],
        p: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        # Image quality rules need a file_meta dict. Without one (i.e.
        # called from the endpoint layer that doesn't compute Laplacian
        # variance yet), silently skip — the W3+ worker will run them.
        if not file_meta:
            return None
        if p.get("laplacian_variance_min") is not None:
            var = file_meta.get("blur_laplacian_var")
            if var is not None and float(var) < float(p["laplacian_variance_min"]):
                return {
                    "code": code,
                    "severity": sev,
                    "message_key": msg,
                    "details": {"laplacian_var": float(var)},
                }
        if p.get("min_width") is not None and p.get("min_height") is not None:
            w = file_meta.get("width")
            h = file_meta.get("height")
            if w is not None and h is not None:
                if int(w) < int(p["min_width"]) or int(h) < int(p["min_height"]):
                    return {
                        "code": code,
                        "severity": sev,
                        "message_key": msg,
                        "details": {"resolution": f"{w}x{h}"},
                    }
        return None

    def _rule_cross_field(
        self,
        code: str,
        sev: str,
        msg: str,
        fields: dict[str, Any],
        p: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        a = self._parse_date(fields.get(p["fields"][0]))
        b = self._parse_date(fields.get(p["fields"][1]))
        if a is None or b is None:
            # 1.1.2a expects `missing_field_fails` to surface — if
            # departure_date is missing, treat as ordering violation.
            if fields.get(p["fields"][0]) and not fields.get(p["fields"][1]):
                return {
                    "code": code,
                    "severity": sev,
                    "message_key": msg,
                    "details": {
                        "fields": p["fields"],
                        "reason": "departure_missing",
                    },
                }
            return None
        if b < a:
            return {
                "code": code,
                "severity": sev,
                "message_key": msg,
                "details": {
                    "fields": p["fields"],
                    "reason": "departure_before_arrival",
                },
            }
        if p.get("max_days"):
            stay = (b - a).days
            if stay > int(p["max_days"]):
                return {
                    "code": code,
                    "severity": sev,
                    "message_key": msg,
                    "details": {
                        "fields": p["fields"],
                        "stay_days": stay,
                        "max_days": p["max_days"],
                    },
                }
        return None

    def _rule_ocr_confidence(
        self,
        code: str,
        sev: str,
        msg: str,
        fields: dict[str, Any],
        file_meta: Optional[dict[str, Any]],
        p: dict[str, Any],
        materials: Optional[list[MaterialRef]] = None,
    ) -> Optional[dict[str, Any]]:
        min_conf = float(p["min_confidence"])
        # Look for OCR confidences in fields["__ocr__"] (1.1.2a contract)
        # OR in each Material's ocr_result (1.1.1a endpoint contract).
        candidates: list[tuple[dict[str, Any], Optional[int]]] = []
        if isinstance(fields.get("__ocr__"), dict):
            candidates.append((fields["__ocr__"], None))
        for m in materials or []:
            if m.ocr_result:
                candidates.append((m.ocr_result, m.id))

        for src, mid in candidates:
            confs: list[float] = []
            for v in src.values():
                if isinstance(v, dict) and "confidence" in v:
                    try:
                        confs.append(float(v["confidence"]))
                    except (TypeError, ValueError):
                        continue
                elif isinstance(v, (int, float)):
                    confs.append(float(v))
            if confs and (sum(confs) / len(confs)) < min_conf:
                return {
                    "code": code,
                    "severity": sev,
                    "message_key": msg,
                    "material_id": mid,
                    "details": {
                        "avg_confidence": round(sum(confs) / len(confs), 3),
                        "min_required": min_conf,
                    },
                }
        return None


# --------------------------------------------------------------------------- #
# Overall verdict                                                             #
# --------------------------------------------------------------------------- #
def overall(issues: list[dict[str, Any]]) -> str:
    """Reduce per-rule issues to a single status: error > warning > pass."""
    sev_rank = {"error": 3, "warning": 2, "info": 1, "pass": 0}
    worst = 0
    for i in issues:
        worst = max(worst, sev_rank.get(i.get("severity", "pass"), 0))
    if worst >= 3:
        return "error"
    if worst >= 2:
        return "warning"
    return "pass"
