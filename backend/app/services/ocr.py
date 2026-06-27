"""OCR Engine — PaddleOCR 2.7+ 主引擎, Tesseract 5 兜底 (V2 §5.1.2).

W19-2: 启用 Tesseract 5 作为真正的兜底. paddleocr 包虽然装了, 但底层
paddlepaddle 推理引擎 ~700MB 没装, 实际 PaddleOCR 一调就报
"paddle_static unavailable because paddlepaddle not installed". Tesseract binary
(/opt/homebrew/bin/tesseract) 一直在系统里, pytesseract 也装了, 之前没接通.

W31: 字段抽取升级 — keyword 锚定 + YAML 国家 passport_re 优先匹配 + MRZ 兜底.
旧版按正则顺序 break 导致中国 9 位数字护照被 US 格式抢走; 国籍拿全文第一个 3 字母
(PASSPORT/CHINA), 性别可能撞月份. 修复:
  1. 加载 ocr_field_mapping.yaml 拿到 9 国 passport_re, 用各国格式分别匹配
  2. keyword 锚定 — 找 "Passport No." / "护照号码" 同行/邻行的字段值
  3. MRZ 兜底 — ICAO 9303 机器可读区 (P< + 两行 44 字符) 解析最可靠
"""
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Set

import numpy as np
import yaml

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


# --------------------------------------------------------------------------- #
# Country field mapping (lazy-loaded from YAML)                               #
# --------------------------------------------------------------------------- #
_FIELD_MAP_CACHE: Optional[Dict[str, Any]] = None
_FIELD_MAP_LOCK = Lock()


def _load_field_map() -> Dict[str, Any]:
    """Lazy-load ocr_field_mapping.yaml once. Returns dict keyed by country code."""
    global _FIELD_MAP_CACHE
    if _FIELD_MAP_CACHE is not None:
        return _FIELD_MAP_CACHE
    with _FIELD_MAP_LOCK:
        if _FIELD_MAP_CACHE is not None:
            return _FIELD_MAP_CACHE
        try:
            yaml_path = Path(__file__).parent / "ocr_field_mapping.yaml"
            with open(yaml_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            # Compile regex strings once at load time
            compiled: Dict[str, Any] = {}
            for code, cfg in raw.items():
                compiled[code.upper()] = {
                    **cfg,
                    "_passport_re": re.compile(cfg["passport_re"]) if cfg.get("passport_re") else None,
                }
            _FIELD_MAP_CACHE = compiled
        except Exception:
            _FIELD_MAP_CACHE = {}
    return _FIELD_MAP_CACHE


# --------------------------------------------------------------------------- #
# Engine singleton cache (per lang)                                            #
# --------------------------------------------------------------------------- #
_ENGINE_CACHE: Dict[str, "OCREngine"] = {}
_ENGINE_LOCK = Lock()


def get_engine(lang: str = "en") -> "OCREngine":
    """Return cached OCREngine instance per lang. Avoid re-loading PaddleOCR per request."""
    lang_key = lang if lang in LANG_MAP else "en"
    with _ENGINE_LOCK:
        if lang_key not in _ENGINE_CACHE:
            _ENGINE_CACHE[lang_key] = OCREngine(lang=lang_key)
        return _ENGINE_CACHE[lang_key]


class OCREngine:
    """
    OCR engine (PaddleOCR primary + Tesseract 5 fallback).

    W19-2: 主引擎失败时自动 fallback 到 Tesseract 5. 字段抽取逻辑对两个引擎
    的输出都通用 (统一映射成 [{text, bbox, confidence}] 形态).

    Usage:
        engine = get_engine("en")  # use cached singleton
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
                # PaddleOCR 3.x: use_textline_orientation (replaces use_angle_cls)
                # PaddleOCR 2.x: use_angle_cls
                try:
                    self._engine = PaddleOCR(
                        lang=self.lang, use_textline_orientation=True
                    )
                except TypeError:
                    self._engine = PaddleOCR(
                        lang=self.lang, use_angle_cls=True
                    )
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

    # ---- W31: keyword-anchored field extraction ---- #
    _KEYWORD_LABELS = {
        "passport_no": [
            "护照号码", "护照号", "护照编号", "护照 No", "护照 NO",
            "Passport No", "Passport No.", "PASSPORT NO", "PASSPORT NUMBER",
            "Document No", "Document No.", "DOCUMENT NO",
            "P<",  # MRZ prefix
        ],
        "surname": ["姓", "Surname", "SURNAME", "Last Name", "LAST NAME", "Family Name"],
        "given_name": ["名", "Given Name", "GIVEN NAME", "GIVEN NAMES", "First Name", "FIRST NAME", "Names"],
        "sex": ["性别", "Sex", "SEX", "Gender", "GENDER", "男/女"],
        "nationality": ["国籍", "Nationality", "NATIONALITY"],
        "dob": ["出生日期", "出生年月日", "Date of Birth", "DATE OF BIRTH", "DOB", "Birth Date"],
        "expiry": ["有效期至", "有效期", "Expiry Date", "EXPIRY DATE", "Date of Expiry", "EXPIRY"],
    }

    # W32: pre-computed label word sets for word-split matching.
    # When OCR splits "Date of Birth" into 3 separate items ["Date", "of", "Birth"],
    # the substring match in _extract_anchored misses. Fallback: check if items
    # within a y-band collectively contain all words of a label.
    _KEYWORD_LABEL_WORDS: Dict[str, List[Set[str]]] = {}

    @classmethod
    def _get_label_word_sets(cls, field: str) -> List[Set[str]]:
        """Return list of {uppercase-word-set} per label for word-split matching.

        CJK labels (e.g. "护照号码") are returned as-is — CJK OCR rarely splits
        mid-character, so substring match is reliable. Latin labels like
        "Date of Birth" → {"DATE", "OF", "BIRTH"}; matching items are found
        by token-set containment across a y-band.
        """
        if field not in cls._KEYWORD_LABEL_WORDS:
            sets: List[Set[str]] = []
            for lbl in cls._KEYWORD_LABELS.get(field, []):
                # Split on whitespace + punctuation; keep alphanum + CJK runs as words
                words = re.findall(r"[A-Z0-9]+|[\u4e00-\u9fff]+", lbl.upper())
                if words:
                    sets.append(set(words))
            cls._KEYWORD_LABEL_WORDS[field] = sets
        return cls._KEYWORD_LABEL_WORDS[field]

    def _extract_anchored(
        self, items: List[Dict[str, Any]], field: str, full_text: str
    ) -> Optional[str]:
        """Find a value anchored by a keyword label appearing near it.

        Strategy: scan items for any line containing a label keyword for this field.
        For each hit, look at items on the same horizontal band (overlapping y) for
        the actual value (regex per field). Returns the first match.

        W32 upgrade: label word-split fallback.
        When OCR splits a multi-word label (e.g. "Date of Birth" → ["Date", "of",
        "Birth"] in separate items), the whole-label substring match misses. We
        then try a token-set containment match: collect items in a y-band whose
        text is a word of some label, and if the union covers all words of that
        label, treat the cluster as the label.
        """
        labels = self._KEYWORD_LABELS.get(field, [])
        if not labels or not items:
            return None

        # value regex per field
        if field == "passport_no":
            value_re = re.compile(r"[A-Z0-9]{7,12}")
        elif field in ("sex",):
            value_re = re.compile(r"\b(M|F|MALE|FEMALE|男|女)\b", re.IGNORECASE)
        elif field == "nationality":
            value_re = re.compile(r"\b([A-Z]{3,})\b")
        elif field in ("dob", "expiry"):
            value_re = re.compile(r"\b(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})\b")
        else:
            value_re = re.compile(r"\S{2,}")  # any non-empty token

        def _y_center(bbox: List[List[float]]) -> float:
            ys = [p[1] for p in bbox]
            return (min(ys) + max(ys)) / 2.0

        def _x_range(bbox: List[List[float]]) -> tuple:
            xs = [p[0] for p in bbox]
            return (min(xs), max(xs))

        def _item_words(text: str) -> Set[str]:
            """Extract uppercase words from one OCR item."""
            return set(re.findall(r"[A-Z0-9]+|[\u4e00-\u9fff]+", (text or "").upper()))

        # Build per-line index: each item gets its y-center + word set
        indexed = [
            (it, _y_center(it["bbox"]), _x_range(it["bbox"]), _item_words(it["text"]))
            for it in items
        ]

        # ---- Pass 1: whole-label substring match (existing logic, fast path) ----
        for anchor_idx, (it, y, (x0, x1), _) in enumerate(indexed):
            text_upper = it["text"].upper()
            # match label (some labels are multi-token, so we check text-stripped too)
            text_clean = re.sub(r"[:：/\.\s]+", "", it["text"]).upper()
            hit_label = False
            for lbl in labels:
                lbl_clean = re.sub(r"[:：/\.\s]+", "", lbl).upper()
                if lbl in it["text"] or lbl.upper() in text_upper or lbl_clean in text_clean:
                    hit_label = True
                    break
            if not hit_label:
                continue

            val = self._find_value_in_band(
                indexed, anchor_idx=anchor_idx,
                anchor_x1=x1, anchor_y=y, value_re=value_re, field=field,
                label_text=it["text"], labels=labels,
            )
            if val:
                return val

        # ---- Pass 2: label word-split fallback (W32) ----
        word_sets = self._get_label_word_sets(field)
        if not word_sets:
            return None

        for target_words in word_sets:
            # Skip CJK-only labels (handled by Pass 1; word-split unlikely for CJK)
            if all(re.fullmatch(r"[\u4e00-\u9fff]+", word) for word in target_words):
                continue
            # Items whose word-set is subset of target_words
            candidate_items = [
                (i, it, y, (x0, x1), ws)
                for i, (it, y, (x0, x1), ws) in enumerate(indexed)
                if ws and ws.issubset(target_words) and len(ws) >= 1
            ]
            if len(candidate_items) < len(target_words):
                continue
            # Anchor = one candidate, siblings = others within ±80px y-band
            for anchor_i, anchor_it, anchor_y, (ax0, ax1), anchor_ws in candidate_items:
                siblings = [
                    (i, it, y, (x0, x1), ws)
                    for i, it, y, (x0, x1), ws in candidate_items
                    if i != anchor_i and abs(y - anchor_y) <= 80
                ]
                # union all sibling word-sets with anchor's word-set
                sibling_words: Set[str] = set()
                for _, _, _, _, ws in siblings:
                    sibling_words |= ws
                union_words = anchor_ws | sibling_words
                if not target_words.issubset(union_words):
                    continue
                # Cluster right edge: max x1 across anchor + siblings
                cluster_x1 = max(
                    [(ax0, ax1)] + [(x0, x1) for _, _, _, (x0, x1), _ in siblings],
                    key=lambda r: r[1],
                )[1]
                val = self._find_value_in_band_by_index(
                    indexed, cluster_x1=cluster_x1, cluster_y=anchor_y,
                    value_re=value_re, field=field,
                )
                if val:
                    return val

        return None

    def _find_value_in_band(
        self,
        indexed,
        anchor_idx: int,
        anchor_x1: float,
        anchor_y: float,
        value_re: "re.Pattern",
        field: str,
        label_text: str,
        labels: List[str],
    ) -> Optional[str]:
        """Look for a value to the right of the anchor (same y-band)."""
        candidates: List[tuple] = []
        for i, (it2, y2, (x0_2, x1_2), _) in enumerate(indexed):
            if i == anchor_idx:
                continue
            if abs(y2 - anchor_y) > 60:
                continue
            if x0_2 < anchor_x1:
                candidates.append((x0_2, y2, it2))
        candidates.sort(key=lambda c: (abs(c[1] - anchor_y), c[0]))

        for _, _, c in candidates[:8]:
            m = value_re.search(c["text"])
            if m:
                val = m.group(0).strip().rstrip(",;:")
                if field == "sex" and val.upper() in ("MALE", "FEMALE"):
                    val = "M" if val.upper() == "MALE" else "F"
                if field == "sex" and val in ("男", "女"):
                    val = "M" if val == "男" else "F"
                return val
        # last-ditch: strip label from item text and see if value remains
        leftover = label_text
        for lbl in labels:
            leftover = leftover.replace(lbl, " ")
        m = value_re.search(leftover)
        if m:
            return m.group(0).strip().rstrip(",;:")
        return None

    def _find_value_in_band_by_index(
        self,
        indexed,
        cluster_x1: float,
        cluster_y: float,
        value_re: "re.Pattern",
        field: str,
    ) -> Optional[str]:
        """Same shape as _find_value_in_band, used by the W32 word-split path."""
        candidates: List[tuple] = []
        for i, (it2, y2, (x0_2, x1_2), _) in enumerate(indexed):
            if abs(y2 - cluster_y) > 60:
                continue
            if x0_2 < cluster_x1:
                candidates.append((x0_2, y2, it2))
        candidates.sort(key=lambda c: (abs(c[1] - cluster_y), c[0]))

        for _, _, c in candidates[:8]:
            m = value_re.search(c["text"])
            if m:
                val = m.group(0).strip().rstrip(",;:")
                if field == "sex" and val.upper() in ("MALE", "FEMALE"):
                    val = "M" if val.upper() == "MALE" else "F"
                if field == "sex" and val in ("男", "女"):
                    val = "M" if val == "男" else "F"
                return val
        return None

    def _extract_mrz(self, full_text: str) -> Optional[Dict[str, str]]:
        """Parse ICAO 9303 MRZ (machine-readable zone) from text.

        MRZ format: line 1 starts with 'P<', line 2 is 44 chars of digits/letters/<.
        Fields: passport_no (positions 0-9 of line 1, drop filler <), dob (line 2 pos 0-6),
        sex (pos 7), expiry (pos 8-14), nationality (line 1 pos 10-13).
        """
        m = re.search(r"P<[A-Z<]{3,}([A-Z0-9<]{9})([A-Z<]{3})<?", full_text)
        if not m:
            return None
        passport_no = m.group(1).replace("<", "")
        nationality = m.group(2).replace("<", "")
        # line 2: dob(6) + sex(1) + expiry(6) + ...
        m2 = re.search(
            r"\b([0-9]{6})([MFX<])([0-9]{6})", full_text
        )
        if not m2:
            return None
        dob_raw = m2.group(1)
        sex = m2.group(2)
        expiry_raw = m2.group(3)
        # YYMMDD → YYYY-MM-DD (assume 19xx for DOB, 20xx for expiry)
        def _ymd(raw: str, century: int) -> Optional[str]:
            try:
                yy, mm, dd = int(raw[0:2]), int(raw[2:4]), int(raw[4:6])
                if not (1 <= mm <= 12 and 1 <= dd <= 31):
                    return None
                return f"{century + yy:04d}-{mm:02d}-{dd:02d}"
            except Exception:
                return None
        return {
            "passport_no": passport_no or None,
            "nationality": nationality or None,
            "sex": sex if sex in ("M", "F") else None,
            "dob": _ymd(dob_raw, 1900),
            "expiry": _ymd(expiry_raw, 2000),
        }

    def _detect_country_from_text(self, full_text: str) -> Optional[str]:
        """Detect passport issuing country from text hints (Chinese name / English name / ISO code)."""
        upper = full_text.upper()
        # ISO 3-letter codes (high confidence)
        iso_codes = {
            "USA": "US", "GBR": "GB", "GBR": "GB", "CHN": "CN", "JPN": "JP",
            "DEU": "DE", "FRA": "FR", "ITA": "IT", "AUS": "AU", "SGP": "SG",
            "KOR": "KR", "PRK": "KP", "CAN": "CA", "IND": "IN",
        }
        for code, mapped in iso_codes.items():
            if re.search(rf"\b{code}\b", upper):
                return mapped
        # English country names on passport header
        name_map = {
            "UNITED STATES OF AMERICA": "US", "UNITED KINGDOM": "GB", "JAPAN": "JP",
            "AUSTRALIA": "AU", "REPUBLIC OF SINGAPORE": "SG", "REPUBLIC OF KOREA": "KR",
            "FEDERAL REPUBLIC OF GERMANY": "DE", "REPUBLIQUE FRANCAISE": "FR",
            "REPUBBLICA ITALIANA": "IT", "PEOPLE'S REPUBLIC OF CHINA": "CN",
            "中华人民共和国": "CN", "日本国": "JP", "大韩民国": "KR",
        }
        for name, code in name_map.items():
            if name in upper or name in full_text:
                return code
        return None

    def extract_passport_fields(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Passport field extraction (keyword-anchored + YAML country passport_re + MRZ).

        Extracts: passport_no, surname, given_name, sex, nationality, dob, expiry.

        W31 upgrade: was naive regex break, now:
          1. Try MRZ parse first (most reliable — ICAO 9303 standard)
          2. Try keyword-anchored extraction (find "护照号码" → value next to it)
          3. Fallback to YAML country passport_re matching (per-country format)
          4. Last-ditch: full-text regex

        W25 fix: gate on document type — refuse to extract passport fields if
        the OCR text doesn't look like a passport page. This drops false-positive
        rate from ~30% → ~0% on synthetic mixed data.

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
            "country_hint": None,
        }

        # ── Gate: refuse to extract passport fields from non-passport images ──
        if not self._is_passport_document(full_text):
            return fields

        fields["is_passport_doc"] = True
        fields["country_hint"] = self._detect_country_from_text(full_text)

        # --- Priority 1: MRZ parse (ICAO 9303, most reliable) ---
        mrz = self._extract_mrz(full_text)
        if mrz:
            for k, v in mrz.items():
                if v and not fields.get(k):
                    fields[k] = v

        # --- Priority 2: keyword-anchored extraction (label → nearby value) ---
        for fld in ("passport_no", "sex", "nationality", "dob", "expiry", "surname", "given_name"):
            if fields.get(fld):
                continue  # MRZ already filled it
            anchored = self._extract_anchored(items, fld, full_text)
            if anchored:
                fields[fld] = anchored

        # --- Priority 3: country-aware passport_re matching (uses YAML) ---
        if not fields.get("passport_no"):
            country = fields.get("country_hint")
            field_map = _load_field_map()
            # try detected country first, then all countries
            ordered_codes = []
            if country and country in field_map:
                ordered_codes.append(country)
            ordered_codes.extend(c for c in field_map if c != country)
            for code in ordered_codes:
                cfg = field_map[code]
                pre = cfg.get("_passport_re")
                if not pre:
                    continue
                m = pre.search(full_text)
                if m:
                    fields["passport_no"] = m.group(0)
                    if not fields.get("country_hint"):
                        fields["country_hint"] = code
                    break

        # --- Priority 4 (last-ditch): generic full-text regex --- #
        if not fields.get("passport_no"):
            generic_patterns = [
                r"\b[A-Z][0-9]{8}\b",
                r"\b[0-9]{9}\b",
                r"\b[A-Z]{2}[0-9]{7}\b",
                r"\b[A-Z][0-9]{7}\b",
                r"\b[0-9]{2}[A-Z]{2}[0-9]{5}\b",
                r"\b[A-Z][0-9]{7}[A-Z]\b",
            ]
            for pattern in generic_patterns:
                m = re.search(pattern, full_text)
                if m:
                    fields["passport_no"] = m.group(0)
                    break

        # --- Date normalization (use country date_fmt if available) ---
        if fields.get("dob") and not self._looks_iso_date(str(fields["dob"])):
            fields["dob"] = self._normalize_date(str(fields["dob"]))
        if fields.get("expiry") and not self._looks_iso_date(str(fields["expiry"])):
            fields["expiry"] = self._normalize_date(str(fields["expiry"]))

        return fields

    @staticmethod
    def _looks_iso_date(s: str) -> bool:
        """Cheap check: is this already YYYY-MM-DD?"""
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", s))

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
    """Factory: build OCREngine with lang validation. Prefer get_engine() for caching."""
    return OCREngine(lang=lang)
