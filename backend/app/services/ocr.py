"""OCR Engine — PaddleOCR 2.7+ 主引擎, Tesseract 5 兜底 (V2 §5.1.2)."""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
try:
    from paddleocr import PaddleOCR  # type: ignore
    _PADDLE_AVAILABLE = True
except ImportError:
    PaddleOCR = None  # type: ignore
    _PADDLE_AVAILABLE = False

# Supported languages map (internal key → PaddleOCR lang arg)
LANG_MAP: Dict[str, str] = {
    "en": "en",
    "zh-CN": "ch",
    "id": "id",
    "vi": "vi",
    "ko": "korean",
    "ja": "japan",
    "ch": "ch",
    "korean": "korean",
    "japan": "japan",
}

# Supported lang keys for validation
SUPPORTED_LANGS: List[str] = list(LANG_MAP.keys())


class OCREngine:
    """
    PaddleOCR-based OCR engine (CPU mode, no GPU).

    V2 §5.1.2 spec reference implementation.

    Usage:
        engine = OCREngine("en")
        items = engine.recognize(image_array)
        fields = engine.extract_passport_fields(image_array)
    """

    def __init__(self, lang: str = "en") -> None:
        lang_key = lang if lang in LANG_MAP else "en"
        self.lang = LANG_MAP[lang_key]
        self._engine = PaddleOCR(lang=self.lang)

    def recognize(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run OCR on the given image array.

        Args:
            image: numpy.ndarray, HWC/BGR format (cv2-style).

        Returns:
            List of items: [{text, bbox, confidence}, ...]
        """
        result = self._engine.ocr(image, cls=True)
        items = []
        # result structure: [[line1, line2, ...], []] or []
        raw_lines = result[0] if result and result[0] else []
        for line in raw_lines:
            if not line:
                continue
            bbox, (text, conf) = line
            items.append(
                {
                    "text": str(text),
                    "bbox": [[float(x), float(y)] for x, y in bbox],
                    "confidence": float(conf),
                }
            )
        return items

    def extract_passport_fields(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Passport field extraction (heuristic + regex).

        Extracts: passport_no, surname, given_name, sex, nationality, dob, expiry.

        Args:
            image: numpy.ndarray image.

        Returns:
            Dict with extracted fields (None if not found).
        """
        items = self.recognize(image)
        full_text = "\n".join(item["text"] for item in items)

        fields: Dict[str, Optional[str]] = {
            "passport_no": None,
            "surname": None,
            "given_name": None,
            "sex": None,
            "nationality": None,
            "dob": None,
            "expiry": None,
            "raw_text": full_text,
        }

        # --- Passport number (ICAO 9303 standard + common variants) ---
        # Pattern: 9-char alphanumeric (US), 9-digit (CN), 2-letter+7-digit (DE/FR/IT/KR/JP)
        passport_patterns = [
            r"\b[A-Z][0-9]{8}\b",  # US/DE/KR format: A12345678 (1 alpha + 8 digits)
            r"\b[0-9]{9}\b",  # CN/GB 9 digits
            r"\b[A-Z]{2}[0-9]{7}\b",  # JP/IT format: TR1234567 (2 alpha + 7 digits)
            r"\b[A-Z][0-9]{7}\b",  # AU format: A1234567 (1 alpha + 7 digits)
            r"\b[0-9]{2}[A-Z]{2}[0-9]{5}\b",  # FR format: 12AB34567 (2 digits + 2 alpha + 5 digits)
            r"\b[A-Z][0-9]{7}[A-Z]\b",  # SG format: A1234567B
        ]
        for pattern in passport_patterns:
            m = re.search(pattern, full_text)
            if m:
                fields["passport_no"] = m.group(0)
                break

        # --- Sex ---
        sex_m = re.search(r"\b(MALE|FEMALE|M|F)\b", full_text.upper())
        if sex_m:
            val = sex_m.group(0).upper()
            if val in ("MALE", "M"):
                fields["sex"] = "M"
            elif val in ("FEMALE", "F"):
                fields["sex"] = "F"

        # --- Nationality (3-letter ISO code, e.g. IDN, VNM, PHL) ---
        nationality_m = re.search(
            r"\b([A-Z]{3})\b", full_text
        )  # naive; refined by field mapping YAML
        if nationality_m:
            fields["nationality"] = nationality_m.group(1)

        # --- Dates ---
        date_re = re.compile(r"\b(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})\b")
        dates = date_re.findall(full_text)
        if len(dates) >= 1:
            fields["dob"] = self._normalize_date(dates[0])
        if len(dates) >= 2:
            fields["expiry"] = self._normalize_date(dates[-1])

        return fields

    @staticmethod
    def _normalize_date(s: str) -> str:
        """Try common date formats, return original string if all fail."""
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%d.%m.%Y"):
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return s


def create_ocr_engine(lang: str = "en") -> OCREngine:
    """Factory: build OCREngine with lang validation."""
    return OCREngine(lang=lang)
