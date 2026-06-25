"""Material classifier — auto-detect document type (V2 §4.3.4).

Strategy (deterministic, no ML):
  - filename keyword match (passport.jpg, 身份证.png, bank_statement.pdf ...)
  - filename regex match (passport no format, ID no format, .pdf)
  - OCR field match if available (passport_no, id_no, household_register, ...)
  - OCR text keyword match (full-text scan)

Each hit adds weighted score to a candidate. Top-1 wins. We also surface
the `hints` array so the UI can show *why* we guessed what we guessed
(transparency > black-box for visa docs).

Why not a real ML model?
  - Cold start: zero labels, can't bootstrap supervised model.
  - User confirm step in the UX means we can correct + learn later.
  - Visa docs have a small, well-defined type taxonomy (7 classes in V2).
  - When users correct us, store in classification_corrected for later
    gradient-based retraining (out of scope for now).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------- #
# Constants                                                         #
# ---------------------------------------------------------------- #
# weight per source — filename > OCR field > OCR text > mime
_WEIGHT_FILENAME_KEYWORD = 3.0
_WEIGHT_FILENAME_REGEX = 2.0
_WEIGHT_OCR_FIELD = 4.0       # strongest signal (a parsed passport_no is gold)
_WEIGHT_OCR_TEXT = 1.0
_WEIGHT_MIME = 0.5

# Material type taxonomy — must match app.models.material.MATERIAL_TYPES
_TYPES = (
    "passport",
    "id_card",
    "household",
    "enrollment",
    "photo",
    "form",
    "other",
)

# ---------------------------------------------------------------- #
# Keyword + regex patterns                                          #
# ---------------------------------------------------------------- #
# filename → (material_type, weight) — Chinese + English
_FILENAME_KEYWORDS: Dict[str, List[Tuple[str, float]]] = {
    "passport": [
        ("passport", _WEIGHT_FILENAME_KEYWORD),
        ("护照", _WEIGHT_FILENAME_KEYWORD),
        ("护照页", _WEIGHT_FILENAME_KEYWORD),
        ("travel_doc", _WEIGHT_FILENAME_KEYWORD * 0.8),
    ],
    "id_card": [
        ("id_card", _WEIGHT_FILENAME_KEYWORD),
        ("身份证", _WEIGHT_FILENAME_KEYWORD),
        ("sfz", _WEIGHT_FILENAME_KEYWORD * 0.9),
        ("居民身份证", _WEIGHT_FILENAME_KEYWORD),
        ("identity_card", _WEIGHT_FILENAME_KEYWORD),
        ("front", _WEIGHT_FILENAME_KEYWORD * 0.5),  # front/back of ID
        ("back", _WEIGHT_FILENAME_KEYWORD * 0.5),
    ],
    "household": [
        ("household", _WEIGHT_FILENAME_KEYWORD),
        ("户口", _WEIGHT_FILENAME_KEYWORD),
        ("户口本", _WEIGHT_FILENAME_KEYWORD),
        ("hukou", _WEIGHT_FILENAME_KEYWORD),
        ("户籍", _WEIGHT_FILENAME_KEYWORD),
    ],
    "enrollment": [
        ("enrollment", _WEIGHT_FILENAME_KEYWORD),
        ("在校", _WEIGHT_FILENAME_KEYWORD),
        ("学籍", _WEIGHT_FILENAME_KEYWORD),
        ("学生证", _WEIGHT_FILENAME_KEYWORD),
        ("student", _WEIGHT_FILENAME_KEYWORD),
        ("证明", _WEIGHT_FILENAME_KEYWORD * 0.4),  # weak — many things are 证明
    ],
    "photo": [
        ("photo", _WEIGHT_FILENAME_KEYWORD),
        ("照片", _WEIGHT_FILENAME_KEYWORD),
        ("头像", _WEIGHT_FILENAME_KEYWORD),
        ("avatar", _WEIGHT_FILENAME_KEYWORD * 0.8),
        ("portrait", _WEIGHT_FILENAME_KEYWORD),
        ("白底", _WEIGHT_FILENAME_KEYWORD * 0.6),
        ("2寸", _WEIGHT_FILENAME_KEYWORD * 0.6),
    ],
    "form": [
        ("form", _WEIGHT_FILENAME_KEYWORD),
        ("申请表", _WEIGHT_FILENAME_KEYWORD),
        ("application_form", _WEIGHT_FILENAME_KEYWORD),
        ("ds160", _WEIGHT_FILENAME_KEYWORD),
        ("ds-160", _WEIGHT_FILENAME_KEYWORD),
        ("ds_160", _WEIGHT_FILENAME_KEYWORD),
        ("签证表", _WEIGHT_FILENAME_KEYWORD),
        ("vaf", _WEIGHT_FILENAME_KEYWORD),
    ],
    # "other" is the catch-all — we don't add explicit keywords
}


# regex patterns that strongly suggest a type (independent of filename)
_FILENAME_REGEX: Dict[str, List[Tuple[str, float]]] = {
    "passport": [
        (r"\b[a-z]?\d{7,9}\b", _WEIGHT_FILENAME_REGEX),  # e.g. "E12345678" anywhere
        (r"passport[_-]?\d{6,}", _WEIGHT_FILENAME_REGEX * 1.2),
    ],
    "id_card": [
        (r"\b[1-9]\d{16}[\dXx]\b", _WEIGHT_FILENAME_REGEX),  # PRC 18-digit ID
        (r"id[_-]?\d{6,}", _WEIGHT_FILENAME_REGEX),
    ],
}


# OCR field → material type — strongest signal
_OCR_FIELDS: Dict[str, List[Tuple[str, float]]] = {
    "passport": [
        ("passport_no", _WEIGHT_OCR_FIELD),
        ("passport_number", _WEIGHT_OCR_FIELD),
        ("passport_country", _WEIGHT_OCR_FIELD),
        ("mrz", _WEIGHT_OCR_FIELD * 1.2),  # machine-readable zone
        ("date_of_birth", _WEIGHT_OCR_FIELD * 0.4),
    ],
    "id_card": [
        ("id_no", _WEIGHT_OCR_FIELD),
        ("id_number", _WEIGHT_OCR_FIELD),
        ("id_card_no", _WEIGHT_OCR_FIELD),
        ("id_name", _WEIGHT_OCR_FIELD * 0.6),
    ],
    "household": [
        ("household_register_no", _WEIGHT_OCR_FIELD),
        ("household_head", _WEIGHT_OCR_FIELD * 0.5),
        ("relationship", _WEIGHT_OCR_FIELD * 0.5),
    ],
    "enrollment": [
        ("student_no", _WEIGHT_OCR_FIELD),
        ("school_name", _WEIGHT_OCR_FIELD * 0.6),
        ("enrollment_year", _WEIGHT_OCR_FIELD * 0.6),
    ],
    "photo": [
        # photos rarely have OCR fields; this is a placeholder
        ("photo_dimensions", _WEIGHT_OCR_FIELD * 0.5),
    ],
    "form": [
        ("application_no", _WEIGHT_OCR_FIELD),
        ("form_id", _WEIGHT_OCR_FIELD * 0.7),
    ],
}


# OCR text keyword match — weak signal, multi-language
_OCR_TEXT_KEYWORDS: Dict[str, List[Tuple[str, float]]] = {
    "passport": [
        ("PASSPORT", _WEIGHT_OCR_TEXT),
        ("护照", _WEIGHT_OCR_TEXT * 1.2),
        ("P<", _WEIGHT_OCR_TEXT * 0.8),  # MRZ prefix
    ],
    "id_card": [
        ("中华人民共和国居民身份证", _WEIGHT_OCR_TEXT * 1.2),
        ("People's Republic of China", _WEIGHT_OCR_TEXT * 0.8),
        ("Identity Card", _WEIGHT_OCR_TEXT),
        ("性别", _WEIGHT_OCR_TEXT * 0.4),  # weak — appears on many docs
        ("民族", _WEIGHT_OCR_TEXT * 0.6),
    ],
    "household": [
        ("户口簿", _WEIGHT_OCR_TEXT * 1.2),
        ("户主", _WEIGHT_OCR_TEXT),
        ("与户主关系", _WEIGHT_OCR_TEXT),
    ],
    "enrollment": [
        ("在校证明", _WEIGHT_OCR_TEXT * 1.2),
        ("学生证", _WEIGHT_OCR_TEXT),
        ("Student Card", _WEIGHT_OCR_TEXT),
        ("教育部", _WEIGHT_OCR_TEXT * 0.6),
    ],
    "form": [
        ("APPLICATION FOR", _WEIGHT_OCR_TEXT),
        ("申请表", _WEIGHT_OCR_TEXT * 1.2),
        ("DS-160", _WEIGHT_OCR_TEXT * 1.2),
        ("NONIMMIGRANT VISA", _WEIGHT_OCR_TEXT * 0.8),
    ],
}


# mime-type nudges — PDFs are common for forms AND for statements/photos.
# We deliberately keep this weak; filename/keywords must drive classification.
_MIME_HINTS: Dict[str, List[Tuple[str, float]]] = {
    # PDFs: don't pre-bias to 'form' — let filename decide.
    # Only add a tiny nudge when nothing else matched.
    "other": [
        ("application/pdf", _WEIGHT_MIME * 0.2),
    ],
}


# ---------------------------------------------------------------- #
# Public types                                                      #
# ---------------------------------------------------------------- #
@dataclass
class Hint:
    source: str           # filename | ocr_field | ocr_text | mime
    match: str
    weight: float


@dataclass
class ClassifyResult:
    material_type: str
    score: float
    reasons: List[str] = field(default_factory=list)


@dataclass
class ClassificationOutput:
    predicted_type: str
    confidence: float
    candidates: List[ClassifyResult]
    hints: List[Hint]


# ---------------------------------------------------------------- #
# Classifier                                                        #
# ---------------------------------------------------------------- #
class MaterialClassifier:
    """Classify a material into one of MATERIAL_TYPES."""

    def classify(
        self,
        *,
        original_filename: str,
        mime_type: str = "",
        ocr_result: Optional[Dict[str, Any]] = None,
    ) -> ClassificationOutput:
        scores: Dict[str, float] = {t: 0.0 for t in _TYPES}
        reasons: Dict[str, List[str]] = {t: [] for t in _TYPES}
        hints: List[Hint] = []

        fname = (original_filename or "").lower()

        # 1. filename keywords
        for mtype, kws in _FILENAME_KEYWORDS.items():
            for kw, w in kws:
                if kw in fname:
                    scores[mtype] += w
                    reasons[mtype].append(f"filename contains '{kw}'")
                    hints.append(Hint("filename", kw, w))

        # 2. filename regex
        for mtype, patterns in _FILENAME_REGEX.items():
            for pat, w in patterns:
                if re.search(pat, fname, flags=re.IGNORECASE):
                    scores[mtype] += w
                    reasons[mtype].append(f"filename matches /{pat}/")
                    hints.append(Hint("filename", pat, w))

        # 3. OCR fields (strongest signal)
        ocr_fields: Dict[str, Any] = {}
        ocr_text: str = ""
        if ocr_result:
            # accept either {"fields": {...}} or flat dict
            ocr_fields = ocr_result.get("fields", {}) if isinstance(ocr_result, dict) else {}
            if not ocr_fields and isinstance(ocr_result, dict):
                ocr_fields = {k: v for k, v in ocr_result.items() if isinstance(v, (str, int, float))}
            ocr_text = (ocr_result.get("text", "") if isinstance(ocr_result, dict) else "") or ""

        for mtype, field_rules in _OCR_FIELDS.items():
            for field_name, w in field_rules:
                if field_name in ocr_fields and ocr_fields[field_name]:
                    scores[mtype] += w
                    reasons[mtype].append(f"OCR extracted {field_name}={ocr_fields[field_name]!r}")
                    hints.append(Hint("ocr_field", field_name, w))

        # 4. OCR text scan
        ocr_text_lower = ocr_text.lower()
        for mtype, kws in _OCR_TEXT_KEYWORDS.items():
            for kw, w in kws:
                if kw.lower() in ocr_text_lower:
                    scores[mtype] += w
                    reasons[mtype].append(f"OCR text contains '{kw}'")
                    hints.append(Hint("ocr_text", kw, w))

        # 5. mime nudges
        mime_norm = (mime_type or "").lower()
        for mtype, mimes in _MIME_HINTS.items():
            for m, w in mimes:
                if m == mime_norm:
                    scores[mtype] += w
                    reasons[mtype].append(f"mime type {mime_norm}")
                    hints.append(Hint("mime", mime_norm, w))

        # fallback — if every score is 0, default to "other"
        max_score = max(scores.values())
        if max_score <= 0:
            return ClassificationOutput(
                predicted_type="other",
                confidence=0.0,
                candidates=[
                    ClassifyResult("other", 0.0, ["no_signal_default"]),
                ],
                hints=[],
            )

        # rank top-3
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top1_type, top1_score = ranked[0]
        # confidence = top1 / (top1 + runner_up) — bounded between 0..1
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        confidence = top1_score / (top1_score + runner_up) if (top1_score + runner_up) > 0 else 0.0
        # scale into [0,1] range via tanh-ish clamp: if top1=10+, confidence ~= 1
        confidence = min(1.0, max(0.0, confidence))

        candidates: List[ClassifyResult] = []
        for mtype, score in ranked[:3]:
            if score <= 0:
                continue
            candidates.append(
                ClassifyResult(
                    material_type=mtype,
                    score=round(score, 3),
                    reasons=reasons[mtype][:5],  # top-5 reasons per candidate
                )
            )

        return ClassificationOutput(
            predicted_type=top1_type,
            confidence=round(confidence, 3),
            candidates=candidates,
            hints=hints,
        )


_default_classifier: Optional[MaterialClassifier] = None


def get_classifier() -> MaterialClassifier:
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = MaterialClassifier()
    return _default_classifier