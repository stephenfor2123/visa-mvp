"""/api/v2/ocr — OCR recognition endpoint (V2 §5.1)."""
import io
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.audit import record_audit
from app.services.image_preprocessor import get_preprocessor
from app.services.ocr import get_engine

router = APIRouter(tags=["ocr"])
_log = get_logger()


# --------------------------------------------------------------------------- #
# Schemas                                                                   #
# --------------------------------------------------------------------------- #
class OCRItemOut(BaseModel):
    """Single recognized text item."""

    text: str
    bbox: List[List[float]]
    confidence: float


class OCRResultOut(BaseModel):
    """Full OCR result: raw items + extracted passport fields."""

    items: List[OCRItemOut]
    fields: dict
    lang: str
    preprocessed: bool = False  # W31: whether ImagePreprocessor ran
    preprocess_warnings: List[str] = []


# --------------------------------------------------------------------------- #
# Helpers                                                                   #
# --------------------------------------------------------------------------- #
def _pdf_to_bgr(content: bytes, dpi: int = 300) -> Optional[bytes]:
    """Render first page of a PDF to JPEG bytes (RGB) for OCR.

    Uses pdf2image (poppler) if available, else PyMuPDF, else raises.
    Returns JPEG bytes or None if no PDF lib available.
    """
    try:
        from pdf2image import convert_from_bytes  # type: ignore

        pages = convert_from_bytes(content, dpi=dpi, first_page=1, last_page=1)
        if not pages:
            return None
        buf = io.BytesIO()
        pages[0].convert("RGB").save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    except Exception:
        pass
    try:
        import fitz  # type: ignore  # PyMuPDF

        doc = fitz.open(stream=content, filetype="pdf")
        if not doc.page_count:
            return None
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("jpeg")
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Endpoint                                                                  #
# --------------------------------------------------------------------------- #
@router.post(
    "/recognize",
    response_model=ApiResponse[OCRResultOut],
    summary="OCR recognize — PaddleOCR with lang parameter",
)
async def recognize(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(..., description="Image file (JPG/PNG/WebP/PDF)"),
    lang: str = Form(default="en", description="OCR language: en/zh-CN/id/vi"),
) -> ApiResponse[OCRResultOut]:
    """
    POST /api/v2/ocr/recognize

    - JWT auth required
    - multipart upload: file + lang
    - Returns: {items: [{text, bbox, confidence}], fields: {passport_no, ...}}

    V2 §5.1 spec: PaddleOCR 2.7+ main engine, Tesseract 5 fallback.

    W31 upgrade: ImagePreprocessor runs first (perspective correction + CLAHE),
    PDF first page is rendered to JPEG, OCREngine is cached per lang.
    """
    content = await file.read()
    file_size = len(content) if content else 0

    # ── W31: detect PDF and convert to JPEG first ──
    content_type = (file.content_type or "").lower()
    is_pdf = content_type == "application/pdf" or content[:4] == b"%PDF"
    if is_pdf:
        pdf_bytes = _pdf_to_bgr(content)
        if pdf_bytes is None:
            await record_audit(
                db,
                actor_type="user",
                actor_id=current_user.id,
                action="ocr.recognize",
                target_type="ocr",
                target_id=None,
                payload={
                    "lang": lang,
                    "file_size": file_size,
                    "result": "pdf_decode_failed",
                    "error": "pdf2image or PyMuPDF not installed",
                },
            )
            await db.commit()
            return ApiResponse[OCRResultOut](
                code="1000",
                message="OK",
                data=OCRResultOut(
                    items=[],
                    fields={"error": "PDF decode failed (install pdf2image or PyMuPDF)"},
                    lang=lang,
                ),
            )
        content = pdf_bytes
        content_type = "image/jpeg"

    # ── W31: ImagePreprocessor (透视矫正 + CLAHE) before OCR ──
    preprocess_warnings: List[str] = []
    preprocessed = False
    pre = get_preprocessor()
    pp_result = pre.preprocess(content, apply_binarize=False)
    if pp_result.corrected:
        content = pp_result.image_bytes
        preprocessed = True
    preprocess_warnings = list(pp_result.warnings or [])

    # ── Decode image (Pillow → BGR) ──
    try:
        image = Image.open(io.BytesIO(content))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        import numpy as np
        import cv2

        img_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        _log.warning("ocr recognize failed to decode image: {}", exc)
        try:
            await record_audit(
                db,
                actor_type="user",
                actor_id=current_user.id,
                action="ocr.recognize",
                target_type="ocr",
                target_id=None,
                payload={
                    "lang": lang,
                    "file_size": file_size,
                    "result": "decode_failed",
                    "error": str(exc),
                },
            )
            await db.commit()
        except Exception as audit_exc:
            _log.warning("audit write failed for ocr: {}", audit_exc)
        return ApiResponse[OCRResultOut](
            code="1000",
            message="OK",
            data=OCRResultOut(
                items=[],
                fields={"error": "Image decode failed"},
                lang=lang,
                preprocessed=preprocessed,
                preprocess_warnings=preprocess_warnings,
            ),
        )

    # ── Run OCR (cached engine per lang) ──
    engine_error = None
    items: list = []
    fields: dict = {}
    try:
        engine = get_engine(lang=lang)  # W31: cached singleton
        items = engine.recognize(img_bgr)
        fields = engine.extract_passport_fields(img_bgr)
    except Exception as exc:
        engine_error = str(exc)
        _log.error("ocr engine error: {}", exc)
        items = []
        fields = {"error": str(exc)}

    # Build response
    item_out_list = [
        OCRItemOut(text=it["text"], bbox=it["bbox"], confidence=it["confidence"])
        for it in items
    ]
    result = OCRResultOut(
        items=item_out_list,
        fields=fields,
        lang=lang,
        preprocessed=preprocessed,
        preprocess_warnings=preprocess_warnings,
    )

    _log.info(
        "ocr recognize user={} lang={} items={} passport_no={} preprocessed={}",
        current_user.id,
        lang,
        len(items),
        fields.get("passport_no"),
        preprocessed,
    )

    # W19-2: 合规审计 — 记录每次 OCR 调用, 含抽取出的关键字段
    # (只记录字段名 + 长度, 不记录 PII 原文)
    try:
        audit_payload = {
            "lang": lang,
            "file_size": file_size,
            "is_pdf": is_pdf,
            "preprocessed": preprocessed,
            "preprocess_warnings": preprocess_warnings,
            "result": "ok" if engine_error is None else "engine_error",
            "items_count": len(items),
            "extracted_fields": {
                k: (bool(v) and len(str(v)) if v else False)
                for k, v in fields.items()
                if k not in ("raw_text", "error")
            },
        }
        if engine_error:
            audit_payload["error"] = engine_error
        await record_audit(
            db,
            actor_type="user",
            actor_id=current_user.id,
            action="ocr.recognize",
            target_type="ocr",
            target_id=None,
            payload=audit_payload,
        )
        await db.commit()
    except Exception as audit_exc:
        _log.warning("audit write failed for ocr: {}", audit_exc)

    return ApiResponse[OCRResultOut](code="1000", message="OK", data=result)