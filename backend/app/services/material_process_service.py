"""Ephemeral material processing — OCR / bank parse in memory, no persistence.

Files are never written to disk. Callers (POST /materials/process) must not
log raw image bytes or store the upload beyond the request lifecycle.
"""
from __future__ import annotations

import json
from io import BytesIO
from typing import Any, Optional

from app.core.logging import get_logger

_log = get_logger()


def process_bytes(
    content: bytes,
    *,
    material_type: str,
    lang: str = "en",
    country_code: str = "",
) -> dict[str, Any]:
    """Run preprocess + OCR (+ bank parser when applicable). Returns a dict only."""
    from app.services.image_preprocessor import get_preprocessor

    pre = get_preprocessor()
    pp_result = pre.preprocess(content, apply_binarize=False)
    is_blurry = pp_result.is_blurry
    is_complete = pp_result.is_complete
    if pp_result.corrected:
        content = pp_result.image_bytes

    fields: dict[str, Any] = {}
    items: list[dict[str, Any]] = []
    pages_processed = 0
    bank_analysis: Optional[dict[str, Any]] = None

    try:
        import cv2
        import numpy as np
        from PIL import Image

        from app.api.v2.ocr import is_pdf_bytes, pdf_pages_to_bgr
        from app.services.ocr import OCREngine

        engine = OCREngine(lang=lang)
        mtype = (material_type or "other").lower()

        if is_pdf_bytes(content):
            all_items: list[dict[str, Any]] = []
            first_page_bgr = None
            for page_idx, jpg_bytes in pdf_pages_to_bgr(content):
                try:
                    page_pil = Image.open(BytesIO(jpg_bytes))
                    if page_pil.mode != "RGB":
                        page_pil = page_pil.convert("RGB")
                    page_bgr = cv2.cvtColor(np.array(page_pil), cv2.COLOR_RGB2BGR)
                    if first_page_bgr is None:
                        first_page_bgr = page_bgr
                    page_items = engine.recognize(page_bgr)
                    for it in page_items:
                        it["page_index"] = page_idx
                    all_items.extend(page_items)
                    pages_processed += 1
                except Exception as page_exc:
                    _log.warning("process pdf page {} failed: {}", page_idx, page_exc)
            items = all_items
            if mtype == "passport" and first_page_bgr is not None:
                fields = engine.extract_passport_fields(first_page_bgr)
        else:
            pil = Image.open(BytesIO(content)).convert("RGB")
            img_bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
            items = engine.recognize(img_bgr)
            if mtype == "passport":
                fields = engine.extract_passport_fields(img_bgr)
            pages_processed = 1

        if mtype == "bank" and items:
            fields, bank_analysis = _parse_bank(items, country_code=country_code)

    except Exception as exc:
        _log.warning("material process failed type={}: {}", material_type, exc)
        fields = {"error": str(exc)}

    ocr_status = "failed" if fields.get("error") else "done"
    out: dict[str, Any] = {
        "material_type": material_type,
        "fields": fields,
        "is_blurry": is_blurry,
        "is_complete": is_complete,
        "ocr_status": ocr_status,
        "pages_processed": pages_processed,
    }
    if bank_analysis is not None:
        out["bank_analysis"] = bank_analysis
    return out


def _parse_bank(
    items: list[dict[str, Any]],
    *,
    country_code: str,
) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    from datetime import datetime

    from app.services.bank_statement_parser import parse_bank_statement, review_rules
    from app.services.material_group import MaterialItem, group_materials, review_group

    source_country = "CN"
    destination = (country_code or "").upper() or None
    mi = MaterialItem(
        material_id="ephemeral",
        user_id=0,
        order_id=None,
        material_type="bank",
        created_at=datetime.utcnow(),
        ocr_items=list(items),
    )
    groups = group_materials([mi])
    if groups:
        parsed = review_group(groups[0], source_country=source_country)
    else:
        parsed = parse_bank_statement(ocr_items=items, source_country=source_country)

    fields = {
        **parsed,
        "is_passport_doc": False,
        "source": "bank_statement_parser",
        "source_country": source_country,
    }
    bank_analysis = None
    try:
        bank_analysis = review_rules(parsed, destination=destination)
        fields["bank_analysis"] = bank_analysis
    except Exception as exc:
        _log.warning("bank review_rules failed: {}", exc)
    return fields, bank_analysis
