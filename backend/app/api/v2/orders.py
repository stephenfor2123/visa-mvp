"""
/api/v2/orders/* — V2 §4.2 Order Service

Endpoints (5 per Story 1.2.1a + 1.2.1b spec + 1.2.2a ETag + 1.2.2b submit):
  - POST   /api/v2/orders                          (create + associate material_ids)
  - GET    /api/v2/orders                          (list, paginated)
  - GET    /api/v2/orders/{order_no}               (detail + ETag, Story 1.2.2a)
  - GET    /api/v2/orders/{order_no}/checklist     (pre-submit snapshot, only `created`)
  - POST   /api/v2/orders/{order_no}/cancel        (only `created` state)
  - POST   /api/v2/orders/{order_no}/submit        (V2 §4.2.4 — created → submitted, signature-locked)

All endpoints require a valid bearer token (V2 §4.2.3).

ETag behaviour (Story 1.2.2a):
  - The detail endpoint computes SHA-256(sort_keys JSON of the order
    payload, excluding `updated_at` and audit-volatile fields).
  - Response headers: `ETag: "..."`, `Cache-Control: private, max-age=5`.
  - If the client sends `If-None-Match: "<etag>"` matching the
    computed value, we return 304 with no body (saves DB write on the
    next 5-second poll window).

Submit (Story 1.2.2b):
  - The client posts back the `signature` it received from /checklist;
    we re-derive the signature from the current order rows and reject
    with 4011 ORDER_SIGNATURE_MISMATCH if they don't match.
  - Status gate: 4010 ORDER_NOT_EDITABLE if status != "created".
  - On success: order.status "created" → "submitted", submitted_at
    stamped, rpa_task_id = uuid4, OrderStatusHistory row appended.
"""
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Annotated, Optional, Union

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.checklist import ChecklistOut
from app.schemas.common import ApiResponse
from app.schemas.order import (
    CancelOrderResponse,
    CreateOrderRequest,
    CreateOrderResponse,
    DeleteDraftResponse,
    DiagnosisCompleteResponse,
    OrderDetailOut,
    OrderListResponse,
    OrderOut,
    PortalSubmittedResponse,
    RefundRequestBody,
    RefundRequestResponse,
    SubmitOrderRequest,
    SubmitOrderResponse,
)
from app.services.order_service import OrderService


router = APIRouter()
_log = get_logger()


# --------------------------------------------------------------------------- #
# ETag helpers                                                                 #
# --------------------------------------------------------------------------- #
# Fields that change every read but don't represent real state changes —
# e.g. `updated_at` is bumped by SQLAlchemy on any unrelated UPDATE on the
# row, which would defeat the cache. Strip them from the hash input.
_ETAG_STRIP_KEYS = frozenset({"updated_at"})


def _compute_etag(payload: dict) -> str:
    """SHA-256 of a stable JSON serialisation of the order detail.

    Uses sort_keys=True so dict ordering doesn't change the hash, and
    FastAPI's `jsonable_encoder` to normalise types the same way the
    response body is encoded (e.g. Decimal → float). Stripping
    `updated_at` keeps the hash stable when SQLAlchemy bumps the row's
    `onupdate=func.now()` on any unrelated UPDATE.

    Returns a quoted strong ETag, e.g. `"abc..."` (no W/ prefix because
    the body bytes are byte-for-byte deterministic).
    """
    from fastapi.encoders import jsonable_encoder

    cleaned = {k: v for k, v in payload.items() if k not in _ETAG_STRIP_KEYS}
    normalised = jsonable_encoder(cleaned)
    serialised = json.dumps(
        normalised, sort_keys=True, ensure_ascii=False
    )
    digest = hashlib.sha256(serialised.encode("utf-8")).hexdigest()
    return f'"{digest}"'


# --------------------------------------------------------------------------- #
# POST /orders                                                                #
# --------------------------------------------------------------------------- #
@router.post(
    "",
    response_model=ApiResponse[CreateOrderResponse],
    status_code=201,
    summary="Create a new visa order (associate material_ids + applicant data)",
)
async def create_order(
    body: CreateOrderRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[CreateOrderResponse]:
    t0 = time.perf_counter()
    service = OrderService(db)
    order = await service.create(
        user_id=current_user.id,
        destination_id=body.destination_id,
        visa_type=body.visa_type,
        material_ids=body.material_ids,
        applicant_data=body.applicant_data,
        aff_code=body.aff_code,
    )
    _log.info(
        "order.create",
        extra={
            "user_id": current_user.id,
            "event_type": "order.create",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "status": "success",
        },
    )
    return ApiResponse[CreateOrderResponse](
        code="1000",
        message="OK",
        data=CreateOrderResponse(
            order=OrderOut.model_validate(
                {
                    "id": order.id,
                    "uuid": order.uuid,
                    "order_no": order.order_no,
                    "user_id": order.user_id,
                    "destination_id": order.destination_id,
                    "visa_type": order.visa_type,
                    "status": order.status,
                    "total_amount": order.total_amount,
                    "currency": order.currency,
                    "rpa_task_id": order.rpa_task_id,
                    "destination_url": order.destination_url,
                    "aff_code": order.aff_code,
                    "material_ids": body.material_ids,
                    "applicant_data": body.applicant_data,
                    "submitted_at": order.submitted_at,
                    "reviewed_at": order.reviewed_at,
                    "closed_at": order.closed_at,
                    "created_at": order.created_at,
                    "updated_at": order.updated_at,
                }
            ),
            order_no=order.order_no,
            status=order.status,
        ),
    )


# --------------------------------------------------------------------------- #
# GET /orders                                                                 #
# --------------------------------------------------------------------------- #
@router.get(
    "",
    response_model=ApiResponse[OrderListResponse],
    summary="List current user's orders (paginated, optional status filter)",
)
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (1-100)"),
    status: Optional[str] = Query(
        None, description="Filter by status: created / submitted / reviewing / ..."
    ),
) -> ApiResponse[OrderListResponse]:
    service = OrderService(db)
    out = await service.list(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
    )
    return ApiResponse[OrderListResponse](
        code="1000",
        message="OK",
        data=OrderListResponse(
            items=[OrderOut(**i) for i in out["items"]],
            page=out["page"],
            page_size=out["page_size"],
            total=out["total"],
            total_pages=out["total_pages"],
        ),
    )


# --------------------------------------------------------------------------- #
# GET /orders/{order_no}                                                      #
# --------------------------------------------------------------------------- #
@router.get(
    "/{order_no}",
    response_model=ApiResponse[OrderDetailOut],
    summary="Order detail (incl. status history + messages + material refs)",
)
async def get_order(
    request: Request,
    order_no: str = Path(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Union[Response, ApiResponse[OrderDetailOut]]:
    """Order detail with ETag / 304 short-circuit (Story 1.2.2a).

    The ETag is computed over the canonical payload (status / history /
    materials / messages), excluding `updated_at`. On a matching
    `If-None-Match` we return a 304 with no body so the client can keep
    using its cached copy for the next 5-second `max-age` window.
    """
    service = OrderService(db)
    out = await service.get_detail(
        user_id=current_user.id, order_no=order_no
    )
    etag = _compute_etag(out)

    # Conditional GET: client says "I already have this version"
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and if_none_match.strip() == etag:
        # Build a minimal 304 — keep ETag + Cache-Control so the client
        # knows its cached body is still authoritative.
        return Response(
            status_code=304,
            headers={
                "ETag": etag,
                "Cache-Control": "private, max-age=5",
            },
        )

    # Full response with caching hints
    resp_body = ApiResponse[OrderDetailOut](
        code="1000",
        message="OK",
        data=OrderDetailOut(**out),
    )
    # FastAPI's default JSON serialiser doesn't expose headers here, so
    # we render manually via Response. This keeps the response shape
    # identical (ApiResponse envelope) while letting us set the cache
    # headers atomically.
    import json

    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(resp_body),
        headers={
            "ETag": etag,
            "Cache-Control": "private, max-age=5",
        },
    )


# --------------------------------------------------------------------------- #
# GET /orders/{order_no}/checklist                                            #
# --------------------------------------------------------------------------- #
@router.get(
    "/{order_no}/checklist",
    response_model=ApiResponse[ChecklistOut],
    summary="Pre-submit checklist (locked snapshot, only available when status='created')",
)
async def get_checklist(
    order_no: str = Path(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ChecklistOut]:
    """V2 §4.2.3 — pre-submit confirmation view.

    Returns everything the user is about to commit to a visa application,
    in a locked, read-only form. The endpoint is only meaningful while the
    order is still in the `created` state; any later status returns 4010.

    The `signature` field is a SHA-256 hash of the snapshot payload —
    the front-end can pass it to a future submit endpoint to prove
    the user saw this exact view.
    """
    service = OrderService(db)
    out = await service.build_checklist(
        user_id=current_user.id, order_no=order_no
    )
    return ApiResponse[ChecklistOut](
        code="1000",
        message="OK",
        data=ChecklistOut(**out),
    )


# --------------------------------------------------------------------------- #
# POST /orders/{order_no}/cancel                                              #
# --------------------------------------------------------------------------- #
@router.post(
    "/{order_no}/cancel",
    response_model=ApiResponse[CancelOrderResponse],
    summary="Cancel an order (only allowed when status='created')",
)
async def cancel_order(
    order_no: str = Path(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[CancelOrderResponse]:
    service = OrderService(db)
    order = await service.cancel(user_id=current_user.id, order_no=order_no)
    cancelled_at = order.closed_at or datetime.now(timezone.utc).replace(tzinfo=None)
    return ApiResponse[CancelOrderResponse](
        code="1000",
        message="OK",
        data=CancelOrderResponse(
            order_no=order.order_no,
            status=order.status,
            cancelled_at=cancelled_at,
        ),
    )


# --------------------------------------------------------------------------- #
# DELETE /orders/{order_no} — W67                                             #
# --------------------------------------------------------------------------- #
@router.delete(
    "/{order_no}",
    response_model=ApiResponse[DeleteDraftResponse],
    status_code=200,
    summary=(
        "Hard-delete a draft order + soft-delete its materials. "
        "Only allowed when status='created' (草稿 / 待提交); non-created "
        "returns 4010 ORDER_NOT_EDITABLE."
    ),
)
async def delete_draft_order(
    order_no: str = Path(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DeleteDraftResponse]:
    """W67 — delete-draft flow.

    Difference vs `POST /cancel`:
      - cancel → status 'closed', order row + materials preserved
      - delete → order row physically removed, materials soft-deleted,
        audit row kept

    Use cancel when the user wants to "put the order away but keep it
    on record"; use delete when the user wants to start fresh with no
    trace. Front-end surfaces both as separate actions in the draft
    detail page.
    """
    service = OrderService(db)
    out = await service.delete_draft(
        user_id=current_user.id, order_no=order_no
    )
    return ApiResponse[DeleteDraftResponse](
        code="1000",
        message="OK",
        data=DeleteDraftResponse(**out),
    )


# --------------------------------------------------------------------------- #
# POST /orders/{order_no}/submit                                              #
# --------------------------------------------------------------------------- #
@router.post(
    "/{order_no}/submit",
    response_model=ApiResponse[SubmitOrderResponse],
    summary=(
        "Submit the order to RPA (created → submitted). "
        "Requires the `signature` from GET /checklist; mismatch → 4011."
    ),
)
async def submit_order(
    body: SubmitOrderRequest,
    order_no: str = Path(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SubmitOrderResponse]:
    """V2 §4.2.4 — lock-and-submit.

    1. The client first calls `GET /checklist` while the order is still
       in `created` and gets back a `signature` (SHA-256 of the locked
       snapshot).
    2. The client then calls this endpoint with the same signature.
    3. The server re-derives the signature from the current order rows
       and rejects with 4011 ORDER_SIGNATURE_MISMATCH if it differs
       (the order rows changed between get-checklist and submit).
    4. The server flips status `created` → `submitted`, stamps
       submitted_at, mints a fresh rpa_task_id, and writes an
       OrderStatusHistory row.
    5. The actual RPA call is not made here — that is W3's job; we just
       mint a fresh correlation handle.
    """
    service = OrderService(db)
    t0 = time.perf_counter()
    out = await service.submit(
        user_id=current_user.id,
        order_no=order_no,
        client_signature=body.signature,
    )
    _log.info(
        "order.submit",
        extra={
            "user_id": current_user.id,
            "event_type": "order.submit",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "status": out["status"],
        },
    )
    return ApiResponse[SubmitOrderResponse](
        code="1000",
        message="OK",
        data=SubmitOrderResponse(
            order_no=out["order_no"],
            status=out["status"],
            submitted_at=out["submitted_at"],
            rpa_task_id=out["rpa_task_id"],
        ),
    )


# --------------------------------------------------------------------------- #
# POST /orders/{order_no}/diagnosis-complete                                  #
# --------------------------------------------------------------------------- #
@router.post(
    "/{order_no}/diagnosis-complete",
    response_model=ApiResponse[DiagnosisCompleteResponse],
    summary="Mark AI diagnosis done (paid → completed).",
)
async def complete_diagnosis(
    order_no: str = Path(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DiagnosisCompleteResponse]:
    service = OrderService(db)
    order = await service.complete_diagnosis(user_id=current_user.id, order_no=order_no)
    return ApiResponse(
        data=DiagnosisCompleteResponse(
            order_no=order.order_no,
            status=order.status,
            diagnosis_completed_at=order.diagnosis_completed_at,
            completed_at=order.completed_at,
        )
    )


# --------------------------------------------------------------------------- #
# POST /orders/{order_no}/portal-submitted                                    #
# --------------------------------------------------------------------------- #
@router.post(
    "/{order_no}/portal-submitted",
    response_model=ApiResponse[PortalSubmittedResponse],
    summary="User confirms embassy portal submission (milestone only).",
)
async def mark_portal_submitted(
    order_no: str = Path(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PortalSubmittedResponse]:
    service = OrderService(db)
    order = await service._get_owned_order(user_id=current_user.id, order_no=order_no)
    unchanged = order.portal_submitted_at is not None
    order = await service.mark_portal_submitted(
        user_id=current_user.id, order_no=order_no, source="user",
    )
    return ApiResponse(
        data=PortalSubmittedResponse(
            order_no=order.order_no,
            portal_submitted_at=order.portal_submitted_at,
            portal_submitted_source=order.portal_submitted_source or "user",
            unchanged=unchanged,
        )
    )


# --------------------------------------------------------------------------- #
# POST /orders/{order_no}/refund-request                                      #
# --------------------------------------------------------------------------- #
@router.post(
    "/{order_no}/refund-request",
    response_model=ApiResponse[RefundRequestResponse],
    summary="User requests a refund (starts refund sub-track).",
)
async def request_refund(
    body: RefundRequestBody,
    order_no: str = Path(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RefundRequestResponse]:
    service = OrderService(db)
    order = await service.request_refund(
        user_id=current_user.id,
        order_no=order_no,
        reason=body.reason,
        amount=body.amount,
    )
    return ApiResponse(
        data=RefundRequestResponse(
            order_no=order.order_no,
            refund_status=order.refund_status,
            refund_requested_at=order.refund_requested_at,
        )
    )
