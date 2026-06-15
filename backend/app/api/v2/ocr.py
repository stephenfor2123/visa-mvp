"""/api/v2/ocr — OCR recognition endpoint (V2 §5.1)."""
from io import BytesIO
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
from app.services.ocr import OCREngine

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
    """
    # Read image bytes
    content = await file.read()

    # Decode image (handle non-PIL formats)
    try:
        image = Image.open(BytesIO(content))
        # Convert to RGB (Pillow may return RGBA or P mode)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        import numpy as np

        img_array = np.array(image)
        # Pillow RGB → OpenCV BGR (PaddleOCR expects BGR)
        import cv2

        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    except Exception as exc:
        _log.warning("ocr recognize failed to decode image: {}", exc)
        return ApiResponse[OCRResultOut](
            code="1000",
            message="OK",
            data=OCRResultOut(items=[], fields={"error": "Image decode failed"}, lang=lang),
        )

    # Run OCR
    try:
        engine = OCREngine(lang=lang)
        items = engine.recognize(img_bgr)
        fields = engine.extract_passport_fields(img_bgr)
    except Exception as exc:
        _log.error("ocr engine error: {}", exc)
        return ApiResponse[OCRResultOut](
            code="1000",
            message="OK",
            data=OCRResultOut(items=[], fields={"error": str(exc)}, lang=lang),
        )

    # Build response
    item_out_list = [
        OCRItemOut(text=it["text"], bbox=it["bbox"], confidence=it["confidence"])
        for it in items
    ]
    result = OCRResultOut(items=item_out_list, fields=fields, lang=lang)

    _log.info(
        "ocr recognize user={} lang={} items={} passport_no={}",
        current_user.id,
        lang,
        len(items),
        fields.get("passport_no"),
    )
    return ApiResponse[OCRResultOut](code="1000", message="OK", data=result)