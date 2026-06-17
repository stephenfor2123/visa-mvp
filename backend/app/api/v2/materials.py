"""
/api/v2/materials/* — V2 §4.3 File Service

Endpoints:
  - POST   /api/v2/materials/upload        (multipart)
  - GET    /api/v2/materials/{id}
  - DELETE /api/v2/materials/{id}          (soft delete)
  - GET    /api/v2/materials/{id}/download (5-min signed URL)
  - POST   /api/v2/materials/validate      (15+ rules per V2 §5.2)
  - GET    /api/v2/materials/_local/{token}?key=...  (signed-URL target,
                                                       no auth needed)

All endpoints except `/_local/...` require a valid bearer token.
"""
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
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.material import (
    DownloadResponse,
    MaterialDetailOut,
    MaterialOut,
    UploadResponse,
    ValidateRequest,
    ValidateResponse,
    ValidationIssue,
    safe_filename,
)
from app.services import storage
from app.services.material_service import MaterialService


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
