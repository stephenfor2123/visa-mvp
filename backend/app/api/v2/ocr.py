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
    is_blurry: bool = False  # 清晰度: image failed the blur-variance check
    is_complete: bool = True  # 完整度: detected document quad touches frame edge → False


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


# W52: 多页 PDF 渲染 — 银行流水/在职证明这类多页材料,以前只 OCR 第 1 页,
# 后面的页面全部被丢掉。设个 MAX_PAGES 保护内存(20 页 × 300dpi 约 80MB JPEG,
# 解析够用,再大就让用户重传)。
MAX_PDF_PAGES = 20


def is_pdf_bytes(content: bytes, content_type: Optional[str] = None) -> bool:
    """判断 bytes 是不是 PDF (header magic 或 content_type)。"""
    if content_type and "pdf" in content_type.lower():
        return True
    return content[:4] == b"%PDF"


def pdf_pages_to_bgr(content: bytes, dpi: int = 300, max_pages: int = MAX_PDF_PAGES):
    """Generator: 逐页把 PDF 渲染成 (page_index, jpeg_bytes)。

    Yields:
        (int, bytes) — page_index 从 1 开始,jpeg_bytes 是该页的 RGB JPEG 编码。
        若 PDF 解码失败,直接 stop iteration(不抛异常,让调用方走 fallback)。
    """
    last_exc = None
    # 优先 pdf2image
    try:
        from pdf2image import convert_from_bytes  # type: ignore

        pages = convert_from_bytes(content, dpi=dpi, first_page=1, last_page=max_pages)
        for idx, pil in enumerate(pages, start=1):
            buf = io.BytesIO()
            pil.convert("RGB").save(buf, format="JPEG", quality=85)
            yield idx, buf.getvalue()
        return
    except Exception as exc:
        last_exc = exc
    # fallback PyMuPDF
    try:
        import fitz  # type: ignore

        doc = fitz.open(stream=content, filetype="pdf")
        total = min(doc.page_count, max_pages)
        for i in range(total):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=dpi)
            yield i + 1, pix.tobytes("jpeg")
        return
    except Exception as exc:
        last_exc = exc
    # 都失败,记一行 warning 后静默 stop — 调用方可以兜底
    _log.warning("pdf render failed ({}); falling back to no-PDF path", last_exc)


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
    is_pdf = is_pdf_bytes(content, file.content_type)
    pdf_pages_jpegs: list = []  # [(page_idx, jpeg_bytes)] 仅 PDF 时填充
    if is_pdf:
        # 一次性收集所有页(最多 MAX_PDF_PAGES),保留 page_index 给 OCR 阶段用
        try:
            for idx, jpg in pdf_pages_to_bgr(content):
                pdf_pages_jpegs.append((idx, jpg))
        except Exception:
            pdf_pages_jpegs = []
        if not pdf_pages_jpegs:
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
        # 兼容旧的单页流程:把第一页 JPEG 当作 content
        content = pdf_pages_jpegs[0][1]
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
    is_blurry = pp_result.is_blurry
    is_complete = pp_result.is_complete

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
                is_blurry=is_blurry,
                is_complete=is_complete,
            ),
        )

    # ── Run OCR (cached engine per lang) ──
    # W52: 多页 PDF — 已经收集到 pdf_pages_jpegs[(idx, jpeg_bytes)] 列表时,
    # 逐页 OCR 后合并 items[]。每条 item 加 page_index 字段标记来源页,
    # 银行流水 parser 不会用它(它只关心 text),但消费者(比如要按页定位
    # 关键交易时)能查得到。非 PDF 路径走单页(img_bgr 已有)。
    engine_error = None
    items: list = []
    fields: dict = {}
    pages_processed = 0
    try:
        engine = get_engine(lang=lang)  # W31: cached singleton
        if is_pdf and pdf_pages_jpegs:
            # 多页路径 — 每页独立 OCR 后合并
            all_items: list = []
            any_error = None
            for page_idx, jpg_bytes in pdf_pages_jpegs:
                try:
                    import numpy as np

                    page_pil = Image.open(io.BytesIO(jpg_bytes))
                    if page_pil.mode not in ("RGB", "L"):
                        page_pil = page_pil.convert("RGB")
                    page_bgr = cv2.cvtColor(np.array(page_pil), cv2.COLOR_RGB2BGR)
                    page_items = engine.recognize(page_bgr)
                    for it in page_items:
                        # 不动原 item,只附加 page_index;消费者用 .get("page_index")
                        # 拿到来源页(从 1 开始)
                        it["page_index"] = page_idx
                    all_items.extend(page_items)
                    pages_processed += 1
                except Exception as page_exc:
                    _log.warning("pdf page {} ocr failed: {}", page_idx, page_exc)
                    any_error = str(page_exc)
                    # 继续下一页
            items = all_items
            # passport fields 只从第 1 页抽(护照首页才有这些字段)
            try:
                first_pil = Image.open(io.BytesIO(pdf_pages_jpegs[0][1]))
                if first_pil.mode not in ("RGB", "L"):
                    first_pil = first_pil.convert("RGB")
                first_bgr = cv2.cvtColor(np.array(first_pil), cv2.COLOR_RGB2BGR)
                fields = engine.extract_passport_fields(first_bgr)
            except Exception as fp_exc:
                _log.warning("pdf first page passport extract failed: {}", fp_exc)
                fields = {}
            if any_error and not all_items:
                # 所有页都失败 — 报告 engine_error
                raise RuntimeError(any_error)
        else:
            # 单页路径 (image 文件)
            items = engine.recognize(img_bgr)
            fields = engine.extract_passport_fields(img_bgr)
            pages_processed = 1
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
        is_blurry=is_blurry,
        is_complete=is_complete,
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