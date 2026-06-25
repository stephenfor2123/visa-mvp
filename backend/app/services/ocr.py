"""OCR Engine — PaddleOCR 2.7+ 主引擎, Tesseract 5 兜底 (V2 §5.1.2).

W19-2: 启用 Tesseract 5 作为真正的兜底. paddleocr 包虽然装了, 但底层
paddlepaddle 推理引擎 ~700MB 没装, 实际 PaddleOCR 一调就报
"paddle_static unavailable because paddlepaddle not installed". Tesseract binary
(/opt/homebrew/bin/tesseract) 一直在系统里, pytesseract 也装了, 之前没接通.
"""
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

# W19-2: tesseract fallback (实测可工作)
try:
    import pytesseract  # type: ignore
    from PIL import Image as _PILImage
    _TESSERACT_AVAILABLE = True
    _TESSERACT_LANG_MAP = {
        "en": "eng",
        "zh-CN": "chi_sim",
        "ch": "chi_sim",
        "id": "eng",  # 印尼语 tesseract 包不一定有, fallback eng
        "vi": "vie",  # 越南语
        "ko": "kor",
        "korean": "kor",
        "ja": "jpn",
        "japan": "jpn",
    }
except ImportError:
    pytesseract = None  # type: ignore
    _PILImage = None  # type: ignore
    _TESSERACT_AVAILABLE = False
    _TESSERACT_LANG_MAP = {}

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
    OCR engine (PaddleOCR primary + Tesseract 5 fallback).

    W19-2: 主引擎失败时自动 fallback 到 Tesseract 5. 字段抽取逻辑对两个引擎
    的输出都通用 (统一映射成 [{text, bbox, confidence}] 形态).

    Usage:
        engine = OCREngine("en")
        items = engine.recognize(image_array)
        fields = engine.extract_passport_fields(image_array)
    """

    def __init__(self, lang: str = "en") -> None:
        lang_key = lang if lang in LANG_MAP else "en"
        self.lang = LANG_MAP[lang_key]
        # W19-2: PaddleOCR 包虽然装了, 但 paddlepaddle 推理后端没装, __init__
        # 会抛 RuntimeError. 包 try/except, 让主引擎不可用时 recognize() 自动
        # 走 Tesseract 兜底.
        self._engine = None
        if _PADDLE_AVAILABLE:
            try:
                self._engine = PaddleOCR(lang=self.lang)
            except Exception:
                # 装包但跑不起来 (paddlepaddle 缺), 留给 recognize() 走 fallback
                self._engine = None

    def _recognize_tesseract(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Tesseract 5 兜底: pytesseract.image_to_data() 拿每 word + bbox + conf.
        输出形态对齐 PaddleOCR: [{text, bbox, confidence}].
        """
        if not _TESSERACT_AVAILABLE:
            raise RuntimeError("Tesseract fallback unavailable: pytesseract/Pillow not installed")
        tess_lang = _TESSERACT_LANG_MAP.get(self.lang, "eng")
        pil_img = _PILImage.fromarray(image)
        try:
            data = pytesseract.image_to_data(
                pil_img, lang=tess_lang, output_type=pytesseract.Output.DICT
            )
        except pytesseract.TesseractError:
            # 语言包缺失, fallback eng
            data = pytesseract.image_to_data(
                pil_img, lang="eng", output_type=pytesseract.Output.DICT
            )
        items: List[Dict[str, Any]] = []
        n = len(data.get("text", []))
        for i in range(n):
            text = (data["text"][i] or "").strip()
            if not text:
                continue
            try:
                conf_raw = float(data.get("conf", [0] * n)[i])
            except (TypeError, ValueError):
                conf_raw = 0.0
            # pytesseract conf 是 -1..100, PaddleOCR 是 0..1, 归一到 0..1
            conf = max(0.0, min(1.0, conf_raw / 100.0)) if conf_raw >= 0 else 0.0
            left = int(data.get("left", [0] * n)[i])
            top = int(data.get("top", [0] * n)[i])
            width = int(data.get("width", [0] * n)[i])
            height = int(data.get("height", [0] * n)[i])
            bbox = [
                [float(left), float(top)],
                [float(left + width), float(top)],
                [float(left + width), float(top + height)],
                [float(left), float(top + height)],
            ]
            items.append({"text": text, "bbox": bbox, "confidence": conf})
        return items

    def recognize(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run OCR on the given image array.

        W19-2: 主引擎 (PaddleOCR) 优先, 失败时自动 fallback 到 Tesseract 5.
        返回形态统一.

        Args:
            image: numpy.ndarray, HWC/BGR format (cv2-style).

        Returns:
            List of items: [{text, bbox, confidence}, ...]
        """
        # W19-2: 主引擎可用就跑 PaddleOCR
        if self._engine is not None:
            try:
                result = self._engine.ocr(image, cls=True)
                items: List[Dict[str, Any]] = []
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
                if items:
                    return items
                # 主引擎跑了但啥也没认出来, 也 fallback 一次
            except Exception:
                # 主引擎抛异常, 直接 fallback
                pass

# W19-2: fallback 到 Tesseract 5
        return self._recognize_tesseract(image)

    def _is_passport_document(self, full_text: str) -> bool:
        """Heuristic: does the OCR text look like a passport page?

        Returns True if at least one passport-keyword hits AND the text contains
        enough structural hints (e.g. 'PASSPORT' or '护照' or 'P<' MRZ prefix).
        """
        if not full_text:
            return False
        upper = full_text.upper()
        # strong signals
        strong_hits = sum(1 for kw in ("PASSPORT", "护照", "P<") if kw in upper or kw in full_text)
        if strong_hits >= 1:
            return True
        # weak signals — at least 2 of these together
        weak_hits = sum(1 for kw in ("SURNAME", "GIVEN NAME", "NATIONALITY", "REPUBLIC", "PASSEPORT") if kw in upper)
        return weak_hits >= 2

    def extract_passport_fields(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Passport field extraction (heuristic + regex).

        Extracts: passport_no, surname, given_name, sex, nationality, dob, expiry.

        W25 fix: gate on document type — refuse to extract passport fields if
        the OCR text doesn't look like a passport page. This drops false-positive
        rate from ~30% → ~0% on synthetic mixed data (verified by batch_ocr_and_bench.py).

        Args:
            image: numpy.ndarray image.

        Returns:
            Dict with extracted fields (None if not found, or if not a passport doc).
        """
        items = self.recognize(image)
        full_text = "\n".join(item["text"] for item in items)

        fields: Dict[str, Optional[Any]] = {
            "passport_no": None,
            "surname": None,
            "given_name": None,
            "sex": None,
            "nationality": None,
            "dob": None,
            "expiry": None,
            "raw_text": full_text,
            "is_passport_doc": False,
        }

        # ── Gate: refuse to extract passport fields from non-passport images ──
        if not self._is_passport_document(full_text):
            return fields

        fields["is_passport_doc"] = True

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
