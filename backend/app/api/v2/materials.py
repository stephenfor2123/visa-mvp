"""
/api/v2/materials/* — V2 §4.3 File Service

Endpoints:
  - POST   /api/v2/materials/upload            (multipart)
  - POST   /api/v2/materials/preprocess       (auto-scan + crop image)  [NEW]
  - POST   /api/v2/materials/classify          (auto-detect material type) [NEW]
  - POST   /api/v2/materials/{id}/classification (user confirms/corrects)  [NEW]
  - POST   /api/v2/materials/diagnose          (AI refusal-risk assessment) [NEW]
  - GET    /api/v2/materials/{id}
  - DELETE /api/v2/materials/{id}              (soft delete)
  - GET    /api/v2/materials/{id}/download     (5-min signed URL)
  - POST   /api/v2/materials/validate          (15+ rules per V2 §5.2)
  - GET    /api/v2/materials/_local/{token}?key=...  (signed-URL target,
                                                       no auth needed)

All endpoints except `/_local/...` require a valid bearer token.
"""
import base64
import json
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.material import Material
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.material import (
    ClassifyResponse,
    ClassifyResult,
    ClassifyHint,
    ConfirmClassificationRequest,
    DiagnoseRequest,
    DiagnoseResponse,
    DiagnoseIssue,
    DownloadResponse,
    MaterialDetailOut,
    MaterialOut,
    PreprocessMeta,
    PreprocessResponse,
    UploadResponse,
    ValidateRequest,
    ValidateResponse,
    ValidationIssue,
    safe_filename,
)
from app.services import storage
from app.services.audit import record_audit
from app.services.image_preprocessor import get_preprocessor
from app.services.material_classifier import get_classifier
from app.services.material_service import MaterialService
from app.services.visa_diagnoser import VisaDiagnoser


router = APIRouter()
_log = get_logger()


# --------------------------------------------------------------------------- #
# /upload                                                                     #
# --------------------------------------------------------------------------- #
@router.post(
    "/upload",
    response_model=ApiResponse[UploadResponse],
    status_code=201,
    summary="Upload a material (multipart/form-data)",
)
async def upload_material(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(..., description="Binary file content"),
    material_type: str = Form(
        ..., description="passport / id_card / household / enrollment / photo / form / other"
    ),
    order_no: Optional[str] = Form(
        None, max_length=64, description="Optional order number to associate"
    ),
) -> ApiResponse[UploadResponse]:
    data = await file.read()
    if not data:
        raise BizException(ErrorCode.INVALID_PARAMS, message="file is empty")

    service = MaterialService(db)
    row, deduplicated = await service.upload(
        user_id=current_user.id,
        original_filename=safe_filename(file.filename or "file"),
        mime_type=file.content_type or "",
        data=data,
        material_type=material_type,
        order_no=order_no,
    )

    base_url = str(request.base_url).rstrip("/")
    download_url = service.build_download_url(row, base_url=base_url)
    thumb = service.build_thumbnail_url(row, base_url=base_url)

    payload = UploadResponse(
        material=MaterialOut.model_validate(row),
        deduplicated=deduplicated,
        download_url=download_url,
        thumbnail_url=thumb,
    )
    return ApiResponse[UploadResponse](code="1000", message="OK", data=payload)


# --------------------------------------------------------------------------- #
# /preprocess — auto-scan + crop image before upload                          #
# --------------------------------------------------------------------------- #
@router.post(
    "/preprocess",
    response_model=ApiResponse[PreprocessResponse],
    summary="Auto-scan + crop a document image (returns processed JPEG + meta)",
)
async def preprocess_image(
    file: UploadFile = File(..., description="Image to preprocess (JPEG/PNG/HEIC)"),
    apply_binarize: bool = Form(
        False,
        description="Apply adaptive binarize (good for receipts/bank statements; off for ID/passport)",
    ),
    force_grayscale: bool = Form(False, description="Force grayscale output"),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PreprocessResponse]:
    """Run the document-scan pipeline on an uploaded image.

    Returns the processed image as base64 (so the frontend can preview inline
    without an extra round-trip). The frontend can then decide whether to
    upload the original or the processed version.
    """
    data = await file.read()
    if not data:
        raise BizException(ErrorCode.INVALID_PARAMS, message="file is empty")

    # 20MB cap on preprocess (we don't persist, just transform in-memory)
    if len(data) > 20 * 1024 * 1024:
        raise BizException(
            ErrorCode.INVALID_PARAMS,
            message="file too large for preprocess (max 20MB)",
        )

    pre = get_preprocessor()
    result = pre.preprocess(
        data,
        force_grayscale=force_grayscale,
        apply_binarize=apply_binarize,
    )

    payload = PreprocessResponse(
        image_base64=base64.b64encode(result.image_bytes).decode("ascii"),
        meta=PreprocessMeta(
            width=result.width,
            height=result.height,
            size_bytes=result.size_bytes,
            mime_type=result.mime_type,
            confidence=result.confidence,
            corrected=result.corrected,
            corners=result.corners,
            stages=result.stages,
            warnings=result.warnings,
            blur_score=result.blur_score,
            is_blurry=result.is_blurry,
            is_complete=result.is_complete,
        ),
    )
    _log.info(
        "material preprocess user={} corrected={} confidence={} stages={} warnings={}",
        current_user.id,
        result.corrected,
        result.confidence,
        result.stages,
        result.warnings,
    )
    return ApiResponse[PreprocessResponse](code="1000", message="OK", data=payload)


# --------------------------------------------------------------------------- #
# /classify — auto-detect material type from filename + OCR                   #
# --------------------------------------------------------------------------- #
@router.post(
    "/classify",
    response_model=ApiResponse[ClassifyResponse],
    summary="Auto-detect material type (filename + OCR + mime heuristics)",
)
async def classify_material(
    file: Optional[UploadFile] = File(
        None,
        description="Optional: raw file to run OCR + classify inline (slow)",
    ),
    material_id: Optional[int] = Form(
        None,
        description="Optional: existing material id — fetch stored OCR + filename",
    ),
    filename: Optional[str] = Form(
        None,
        description="Optional: explicit filename (overrides file.filename)",
    ),
    mime_type: Optional[str] = Form(None, description="Optional: explicit mime"),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ClassifyResponse]:
    """Return a ranked guess of what kind of material this is.

    Three usage modes:
      A. Send `material_id` — server fetches filename + stored OCR.
      B. Send `file`       — server OCRs on the fly + classifies.
      C. Send `filename` + `mime_type` — purely filename-based (fastest).
    """
    ocr_result: Optional[dict] = None
    fname = filename or ""
    mime = mime_type or ""

    if material_id is not None:
        # mode A: pull from DB
        from app.core.db import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            service = MaterialService(db)
            row = await service.get(user_id=current_user.id, material_id=material_id)
        fname = row.original_filename
        mime = row.mime_type
        if row.ocr_result:
            try:
                ocr_result = json.loads(row.ocr_result)
            except (json.JSONDecodeError, TypeError):
                ocr_result = None
    elif file is not None:
        # mode B: OCR on the fly
        fname = fname or file.filename or ""
        mime = mime or file.content_type or ""
        data = await file.read()
        if data:
            try:
                from io import BytesIO
                import cv2
                import numpy as np
                from PIL import Image
                from app.services.ocr import OCREngine
                pil = Image.open(BytesIO(data)).convert("RGB")
                img_bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
                engine = OCREngine(lang="en")
                items = engine.recognize(img_bgr)
                full_text = "\n".join(it["text"] for it in items)
                fields = engine.extract_passport_fields(img_bgr)
                ocr_result = {"fields": fields, "text": full_text, "items": items}
            except Exception as exc:
                _log.warning("classify inline OCR failed: {}", exc)

    # mode C: pure filename is also covered (ocr_result stays None)

    classifier = get_classifier()
    out = classifier.classify(
        original_filename=fname,
        mime_type=mime,
        ocr_result=ocr_result,
    )

    payload = ClassifyResponse(
        predicted_type=out.predicted_type,
        confidence=out.confidence,
        candidates=[
            ClassifyResult(
                material_type=c.material_type,
                score=c.score,
                reasons=c.reasons,
            )
            for c in out.candidates
        ],
        hints=[
            ClassifyHint(source=h.source, match=h.match, weight=h.weight)
            for h in out.hints
        ],
    )
    return ApiResponse[ClassifyResponse](code="1000", message="OK", data=payload)


# --------------------------------------------------------------------------- #
# /{id}/ocr — run OCR on an already-uploaded material and PERSIST the result   #
# --------------------------------------------------------------------------- #
# W36: closes a real gap — `Material.ocr_result` was set to None at upload time
# (material_service.upload()) and nothing anywhere ever wrote to it afterwards
# (the stateless /ocr/recognize endpoint only returns fields to the caller, it
# never touches the DB row). Every downstream consumer that reads
# `material.ocr_result` from the DB (VisaDiagnoser field-level passport checks,
# the order auto-fill draft) always saw an empty dict. This endpoint runs the
# same preprocess+OCR pipeline as /ocr/recognize but against the already-stored
# file, and writes the result back onto the material row.
@router.post(
    "/{material_id}/ocr",
    response_model=ApiResponse[dict],
    summary="Run OCR on a stored material and persist ocr_result",
)
async def run_material_ocr(
    material_id: int = Path(..., ge=1),
    lang: str = Form("en"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    service = MaterialService(db)
    material = await service.get(user_id=current_user.id, material_id=material_id)

    try:
        content = storage.read_bytes(material.storage_key)
    except FileNotFoundError:
        raise BizException(ErrorCode.MATERIAL_STORAGE_ERROR, message="stored file missing")

    pre = get_preprocessor()
    pp_result = pre.preprocess(content, apply_binarize=False)
    is_blurry = pp_result.is_blurry
    is_complete = pp_result.is_complete
    if pp_result.corrected:
        content = pp_result.image_bytes

    fields: dict = {}
    items: list = []
    try:
        from io import BytesIO

        import cv2
        import numpy as np
        from PIL import Image

        from app.services.ocr import OCREngine

        pil = Image.open(BytesIO(content)).convert("RGB")
        img_bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        engine = OCREngine(lang=lang)
        items = engine.recognize(img_bgr)
        fields = engine.extract_passport_fields(img_bgr)
    except Exception as exc:
        _log.warning("material ocr failed material_id={}: {}", material_id, exc)
        fields = {"error": str(exc)}

    # Persist as a FLAT dict (not nested under "fields") — this matches the
    # contract `extractApplicantDraft()` in frontend/web/src/api/orders.js
    # already expects (see makeDemoPassportMaterial() in the same file for
    # the reference shape: passport_no/surname/given_name/... at the top
    # level of ocr_result, not ocr_result.fields.xxx).
    material.ocr_result = json.dumps(fields, ensure_ascii=False)
    material.ocr_status = "failed" if fields.get("error") else "done"
    await db.commit()

    return ApiResponse[dict](
        code="1000",
        message="OK",
        data={
            "material_id": material_id,
            "fields": fields,
            "is_blurry": is_blurry,
            "is_complete": is_complete,
            "ocr_status": material.ocr_status,
        },
    )


# --------------------------------------------------------------------------- #
# /{id}/classification — user confirms or corrects the AI guess               #
# --------------------------------------------------------------------------- #
@router.post(
    "/{material_id}/classification",
    response_model=ApiResponse[MaterialOut],
    summary="Confirm or correct the AI's material_type guess",
)
async def confirm_classification(
    body: ConfirmClassificationRequest,
    material_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[MaterialOut]:
    from app.models.material import MATERIAL_TYPES

    if body.material_type not in MATERIAL_TYPES:
        raise BizException(
            ErrorCode.INVALID_PARAMS,
            message=f"material_type must be one of {sorted(MATERIAL_TYPES)}",
        )

    service = MaterialService(db)
    row = await service.get(user_id=current_user.id, material_id=material_id)

    # store AI's original guess for learning (only if user corrected)
    if not body.confirmed and row.classification != body.material_type:
        row.classification_corrected = body.material_type
        row.material_type = body.material_type
        await db.commit()
        await db.refresh(row)
        await record_audit(
            db,
            actor_type="user",
            actor_id=current_user.id,
            action="material.classification_correct",
            target_type="material",
            target_id=row.id,
            payload={
                "ai_guess": row.classification,
                "user_choice": body.material_type,
            },
        )
        await db.commit()
    elif body.confirmed:
        # user accepts the AI's guess — promote it to material_type (already there)
        row.classification_corrected = None  # no correction needed
        await db.commit()
        await db.refresh(row)

    return ApiResponse[MaterialOut](
        code="1000", message="OK", data=MaterialOut.model_validate(row)
    )


# --------------------------------------------------------------------------- #
# /diagnose — AI refusal-risk assessment                                      #
# --------------------------------------------------------------------------- #
@router.post(
    "/diagnose",
    response_model=ApiResponse[DiagnoseResponse],
    summary="Diagnose refusal risk for an application (rule engine + RAG context)",
)
async def diagnose(
    body: DiagnoseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DiagnoseResponse]:
    """Aggregate completeness, field-level checks, and policy context.

    Returns an overall risk score (0..1), a categorized list of issues, and
    references to the policy documents that informed the diagnosis.
    """
    service = MaterialService(db)
    materials: list[dict] = []
    for mid in body.material_ids:
        try:
            row = await service.get(user_id=current_user.id, material_id=mid)
        except BizException:
            continue
        ocr_parsed = None
        if row.ocr_result:
            try:
                ocr_parsed = json.loads(row.ocr_result)
            except (json.JSONDecodeError, TypeError):
                ocr_parsed = None
        materials.append({
            "id": row.id,
            "material_type": row.material_type,
            "original_filename": row.original_filename,
            "ocr_status": row.ocr_status,
            "ocr_result": ocr_parsed,
        })

    if not materials:
        raise BizException(
            ErrorCode.INVALID_PARAMS,
            message="no valid material_ids provided",
        )

    diagnoser = VisaDiagnoser()
    out = diagnoser.diagnose(
        materials=materials,
        country_code=body.country_code,
        visa_type=body.visa_type,
        fields=body.fields,
    )

    payload = DiagnoseResponse(
        overall_risk=out.overall_risk,
        risk_score=out.risk_score,
        summary=out.summary,
        issues=[
            DiagnoseIssue(
                code=i.code,
                severity=i.severity,
                title=i.title,
                detail=i.detail,
                fix_suggestion=i.fix_suggestion,
                related_material_id=i.related_material_id,
                params=i.params,
            )
            for i in out.issues
        ],
        positives=out.positives,
        policy_refs=out.policy_refs,
        rule_count=out.rule_count,
    )
    return ApiResponse[DiagnoseResponse](code="1000", message="OK", data=payload)


# --------------------------------------------------------------------------- #
# / (list)                                                                    #
# --------------------------------------------------------------------------- #
@router.get(
    "",
    response_model=ApiResponse[list[MaterialOut]],
    summary="List materials for the current user (optional filters)",
)
async def list_materials(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    order_no: Optional[str] = Query(
        None,
        description="Filter by order_no (frontend sends the public order id like 'V2-...')",
    ),
    material_type: Optional[str] = Query(
        None, description="Filter by material_type (passport / photo / form / other)"
    ),
) -> ApiResponse[list[MaterialOut]]:
    # W19: order_no is a public string id, not the DB integer. For now we accept
    # the filter but don't join through Order (orders table is not yet in scope
    # for materials listing in V2). The frontend treats order_no as best-effort.
    service = MaterialService(db)
    rows = await service.list_for_user(
        user_id=current_user.id,
        order_id=None,
        material_type=material_type,
    )
    items = [MaterialOut.model_validate(r) for r in rows]
    return ApiResponse[list[MaterialOut]](code="1000", message="OK", data=items)


# --------------------------------------------------------------------------- #
# /{id}                                                                       #
# --------------------------------------------------------------------------- #
@router.get(
    "/{material_id}",
    response_model=ApiResponse[MaterialDetailOut],
    summary="Get material metadata (incl. parsed ocr_result)",
)
async def get_material(
    material_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[MaterialDetailOut]:
    service = MaterialService(db)
    out = await service.get_detail(user_id=current_user.id, material_id=material_id)
    return ApiResponse[MaterialDetailOut](
        code="1000", message="OK", data=MaterialDetailOut(**out)
    )


# --------------------------------------------------------------------------- #
# /{id}/download — return a fresh 5-min signed URL                            #
# --------------------------------------------------------------------------- #
@router.get(
    "/{material_id}/download",
    response_model=ApiResponse[DownloadResponse],
    summary="Issue a 5-min signed download URL for the material",
)
async def get_download_url(
    request: Request,
    material_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DownloadResponse]:
    service = MaterialService(db)
    row = await service.get(user_id=current_user.id, material_id=material_id)
    base_url = str(request.base_url).rstrip("/")
    url = service.build_download_url(row, base_url=base_url)
    return ApiResponse[DownloadResponse](
        code="1000",
        message="OK",
        data=DownloadResponse(
            url=url,
            expires_in=service.settings.material_url_ttl_seconds,
            filename=row.original_filename,
        ),
    )


# --------------------------------------------------------------------------- #
# /{id} DELETE — soft delete                                                  #
# --------------------------------------------------------------------------- #
@router.delete(
    "/{material_id}",
    response_model=ApiResponse[MaterialOut],
    summary="Soft-delete a material (deleted_at = now, file kept for audit)",
)
async def delete_material(
    material_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[MaterialOut]:
    service = MaterialService(db)
    row = await service.soft_delete(user_id=current_user.id, material_id=material_id)
    return ApiResponse[MaterialOut](
        code="1000", message="OK", data=MaterialOut.model_validate(row)
    )


# --------------------------------------------------------------------------- #
# /validate — run 15+ rules per V2 §5.2                                       #
# --------------------------------------------------------------------------- #
@router.post(
    "/validate",
    response_model=ApiResponse[ValidateResponse],
    summary="Run all enabled validation rules against given materials + fields",
)
async def validate_materials(
    body: ValidateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[ValidateResponse]:
    service = MaterialService(db)
    out = await service.validate_materials(
        user_id=current_user.id,
        material_ids=body.material_ids,
        fields=body.fields,
    )
    issues = [ValidationIssue(**i) for i in out["issues"]]
    payload = ValidateResponse(
        overall=out["overall"],
        issues=issues,
        rule_count=out["rule_count"],
        materials_checked=out["materials_checked"],
        fields_checked=out["fields_checked"],
    )
    return ApiResponse[ValidateResponse](code="1000", message="OK", data=payload)


# --------------------------------------------------------------------------- #
# /_local/{token}?key=...  — internal endpoint hit by signed URLs            #
# No auth required: the HMAC token IS the auth.                              #
# --------------------------------------------------------------------------- #
@router.get(
    "/_local/{token}",
    summary="Internal: serve a file by signed token (no auth header needed)",
    include_in_schema=False,
)
async def fetch_local(
    token: str,
    key: str = Query(..., description="storage_key the token was signed for"),
):
    if not storage.verify_signed_token(token, key):
        raise BizException(
            ErrorCode.MATERIAL_SIGNED_URL_INVALID,
            message="invalid_or_expired_token",
        )
    try:
        abs_path = storage.path_for(key)
    except FileNotFoundError:
        raise BizException(
            ErrorCode.MATERIAL_NOT_FOUND,
            message="file_not_found",
        )
    if not abs_path.exists():
        raise BizException(
            ErrorCode.MATERIAL_NOT_FOUND,
            message="file_not_found",
        )
    # Best-effort mime guess from filename
    import mimetypes
    media_type, _ = mimetypes.guess_type(abs_path.name)
    return FileResponse(abs_path, media_type=media_type or "application/octet-stream")
