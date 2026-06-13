"""/api/v2/insurance/* — B-W8-3 standalone Insurance endpoints (V2 §4.6, Mock-only).

Endpoints (4):
  - POST /api/v2/insurance/quote         — generate a non-binding price quote
  - POST /api/v2/insurance/bind          — promote a quote to a bound policy
  - POST /api/v2/insurance/claim         — file a rejection claim (mock: approved)
  - GET  /api/v2/insurance/{policy_id}   — query policy / claim status

Why a separate set from /orders or /payment?
  - Insurance is an opt-in product the user can attach to ANY order
    (V2 §4.6 spec: "拒签险 = 用户投保, 签证被拒后赔付"). It cuts across
    order / payment / material boundaries and is therefore its own
    domain — its own router, its own service, its own DTOs.
  - V2.1 swap to real insurance SDK (太平洋保险 / 众安保险) lives entirely
    in `app/services/insurance_provider.py`. The 4 endpoints here are
    the public contract and stay unchanged.

Why Mock-only in V2 (Mavis 13:13 拍板):
  - No KYC, no underwriting, no signed API call to a real insurance
    company. The mock is 100% in-process, in-memory, and zero-credential.
  - claim always returns `status="approved"` so the front-end demo flow
    "申请保险 → 拒签 → 一键理赔" can be exercised end-to-end with
    `pytest` alone.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.insurance import (
    BindData,
    BindRequest,
    ClaimData,
    ClaimRequest,
    PolicyData,
    QuoteData,
    QuoteRequest,
)
from app.services.insurance_provider import get_insurance_provider


router = APIRouter()
_log = get_logger()


# --------------------------------------------------------------------------- #
# 1. POST /api/v2/insurance/quote                                              #
# --------------------------------------------------------------------------- #
@router.post(
    "/quote",
    response_model=ApiResponse[QuoteData],
    summary="Generate an insurance quote (mock, in-memory, no creds)",
)
async def post_quote(
    body: QuoteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[QuoteData]:
    """Generate a non-binding price quote.

    V2.1 real channel: this would call the insurance partner's
    underwriting API (Pacific Insurance / ZhongAn) with applicant
    metadata and return a signed quote token. Mock skips that step
    entirely and just returns the deterministic premium computed from
    `(applicant_age, destination_country)`.
    """
    provider = get_insurance_provider()
    result = await provider.quote(
        order_id=body.order_id,
        applicant_age=body.applicant_age,
        destination_country=body.destination_country,
    )
    if not result.get("ok"):
        raise BizException(
            ErrorCode.INVALID_PARAMS, message=result.get("error") or "quote failed"
        )
    _log.info(
        "insurance quote user_id={} order_id={} country={} premium_cents={}",
        current_user.id, body.order_id, body.destination_country, result["premium_cents"],
    )
    return ApiResponse[QuoteData](
        code="1000",
        message="OK",
        data=QuoteData(
            quote_id=result["quote_id"],
            policy_no=result["policy_no"],
            premium_cents=result["premium_cents"],
            coverage_cents=result["coverage_cents"],
            currency=result["currency"],
            created_at=result["created_at"],
        ),
    )


# --------------------------------------------------------------------------- #
# 2. POST /api/v2/insurance/bind                                               #
# --------------------------------------------------------------------------- #
@router.post(
    "/bind",
    response_model=ApiResponse[BindData],
    summary="Bind a quote to an order, minting a concrete policy",
)
async def post_bind(
    body: BindRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[BindData]:
    """Promote a quote to a concrete bound policy on the order.

    Idempotent — re-binding the same `(order_id, quote_id)` returns the
    existing policy without re-charging the premium. The provider layer
    enforces the `order_id` match (defense against a malicious caller
    claiming someone else's quote).
    """
    provider = get_insurance_provider()
    result = await provider.bind(order_id=body.order_id, quote_id=body.quote_id)
    if not result.get("ok"):
        err = result.get("error") or "bind failed"
        # 1004 (NOT_FOUND) for "quote_id=... not found"; 1007 (CONFLICT) for
        # order_id mismatch / already-claimed policy.
        if "not found" in err:
            raise BizException(ErrorCode.NOT_FOUND, message=err)
        raise BizException(ErrorCode.CONFLICT, message=err)
    _log.info(
        "insurance bind user_id={} order_id={} policy_no={} premium_cents={}",
        current_user.id, body.order_id, result["policy_no"], result["premium_cents"],
    )
    return ApiResponse[BindData](
        code="1000",
        message="OK",
        data=BindData(
            policy_id=result["policy_id"],
            policy_no=result["policy_no"],
            status=result["status"],
            bound_at=result.get("bound_at"),
            order_id=result["order_id"],
            premium_cents=result["premium_cents"],
            coverage_cents=result["coverage_cents"],
            currency=result["currency"],
        ),
    )


# --------------------------------------------------------------------------- #
# 3. POST /api/v2/insurance/claim                                              #
# --------------------------------------------------------------------------- #
@router.post(
    "/claim",
    response_model=ApiResponse[ClaimData],
    summary="File a rejection claim (mock: always approved)",
)
async def post_claim(
    body: ClaimRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[ClaimData]:
    """File a claim against the bound policy.

    Mock always returns `status="approved"` and `payout_cents == coverage_cents`.
    V2.1 real channel: this would submit the 拒签信 PDF / image to the
    insurance partner's claim-ops queue, await a human review, and
    disburse via the same mock payment path (or a real one if V2.1 wires
    WxPay). For V2 the demo just stamps "approved" + 0ms.
    """
    provider = get_insurance_provider()
    result = await provider.claim(
        order_id=body.order_id, rejection_reason=body.rejection_reason
    )
    if not result.get("ok"):
        err = result.get("error") or "claim failed"
        if "not found" in err or "no bound policy" in err:
            raise BizException(ErrorCode.NOT_FOUND, message=err)
        raise BizException(ErrorCode.INVALID_PARAMS, message=err)
    _log.info(
        "insurance claim user_id={} order_id={} policy_no={} claim_id={} "
        "payout_cents={}",
        current_user.id, body.order_id, result["policy_no"],
        result["claim_id"], result["payout_cents"],
    )
    return ApiResponse[ClaimData](
        code="1000",
        message="OK",
        data=ClaimData(
            claim_id=result["claim_id"],
            policy_id=result["policy_id"],
            policy_no=result["policy_no"],
            status=result["status"],
            payout_cents=result["payout_cents"],
            approved_at=result.get("approved_at"),
            order_id=result["order_id"],
            rejection_reason=result["rejection_reason"],
        ),
    )


# --------------------------------------------------------------------------- #
# 4. GET /api/v2/insurance/{policy_id}                                         #
# --------------------------------------------------------------------------- #
@router.get(
    "/{policy_id}",
    response_model=ApiResponse[PolicyData],
    summary="Query policy / claim status by policy_id",
)
async def get_policy(
    policy_id: str = Path(..., min_length=4, max_length=128),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PolicyData]:
    """Read the full policy snapshot.

    Used by the front-end "我的保单" page, and by the test suite to
    verify the full quote → bind → claim lifecycle without having to
    re-mock the provider in-line.
    """
    provider = get_insurance_provider()
    snap = provider.get_policy(policy_id)
    if snap is None:
        raise BizException(
            ErrorCode.NOT_FOUND, message=f"policy_id={policy_id} not found"
        )
    return ApiResponse[PolicyData](code="1000", message="OK", data=PolicyData(**snap))
