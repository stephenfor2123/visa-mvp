"""/api/v2/ds160/* — DS-160 browser extension endpoints (W48 v0.2).

Three endpoints:

  POST /api/v2/ds160/code              — issue / refresh a 12-char code
                                         (session auth, user must own the order)

  POST /api/v2/ds160/code/redeem       — exchange code for ApplicantProfile
                                         (NO session — the code IS the credential)

  POST /api/v2/ds160/portal-submitted  — user confirmed DS-160 submitted on ceac.state.gov
                                         (NO session — the code IS the credential;
                                          sets ds160_portal_submitted_at milestone, idempotent)

Design + invariants documented in `browser-extension/DESIGN-v0.2.md`
and `browser-extension/backend-ds160-code-api.md`.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.ds160 import (
    ApplicantProfile,
    InMemoryRateLimiter,
    compute_fingerprint,
    generate_code,
    get_default_rate_limiter,
    has_minimum_fields,
    is_valid_code_format,
    load_applicant_profile,
    normalize_code_input,
)
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.order import Order
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.common import ApiResponse


router = APIRouter(prefix="/ds160", tags=["ds160"])
_log = get_logger()


# Mapping version mirrors frontend/web/src/data/ds160FieldMap.js.  Keep in
# sync manually until we wire a build hook.
DS160_MAPPING_VERSION = "2026.3"
DS160_MAPPING_VERIFIED_DATE: Optional[str] = None  # set after real-table check


# --------------------------------------------------------------------------- #
# Schemas                                                                      #
# --------------------------------------------------------------------------- #

class IssueCodeRequest(BaseModel):
    order_id: int = Field(..., ge=1)
    force_rotate: bool = Field(
        default=False,
        description="User-initiated rotate: invalidate the current code and mint a new one.",
    )


class IssueCodeResponse(BaseModel):
    order_id: int
    code: str
    fingerprint: str
    issued_at: datetime
    unchanged: bool


class RedeemCodeRequest(BaseModel):
    code: str = Field(..., min_length=12, max_length=20)


class RedeemCodeResponse(BaseModel):
    order_id: int
    profile: dict
    fingerprint: str
    mapping_version: str
    mapping_verified_date: Optional[str]
    issued_at: datetime


class PortalSubmittedResponse(BaseModel):
    order_id: int
    ds160_portal_submitted_at: datetime
    unchanged: bool = Field(
        default=False,
        description="True when portal submission was already recorded (idempotent replay).",
    )


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

# Statuses where a DS-160 code is meaningful to mint.  Pre-paid users can
# prefill; paid/submitted/reviewing are also valid because users frequently
# prep the form while the order is being reviewed.  Closed/abnormal/failed
# are blocked because the order is no longer actionable.
_ORDER_READY_STATUSES = frozenset({
    "created", "paid", "completed",
    # legacy
    "submitted", "reviewing", "approved",
})


async def _audit_redeem(
    db: AsyncSession,
    *,
    order: Optional[Order],
    ip: str,
    user_agent: str,
    success: bool,
    error_code: str = "",
    fingerprint_prefix: str = "",
) -> None:
    """Append a row to audit_log so the admin /logs endpoint surfaces it.

    actor_type='system' because /redeem has no user session; actor_id is the
    order's user_id when we know it (helpful for the admin UI to link back).
    """
    payload = json.dumps(
        {
            "ip": ip,
            "user_agent": user_agent[:200],
            "success": success,
            "error": error_code,
            "fingerprint_prefix": fingerprint_prefix,
        },
        ensure_ascii=False,
    )
    db.add(
        AuditLog(
            actor_type="system",
            actor_id=(order.user_id if order else None),
            action="ds160.code.redeem",
            target_type="order",
            target_id=(order.id if order else None),
            payload=payload,
        )
    )
    # Don't await commit here — the caller commits in its own transaction.


async def _audit_portal_submitted(
    db: AsyncSession,
    *,
    order: Optional[Order],
    ip: str,
    user_agent: str,
    success: bool,
    error_code: str = "",
    unchanged: bool = False,
) -> None:
    payload = json.dumps(
        {
            "ip": ip,
            "user_agent": user_agent[:200],
            "success": success,
            "error": error_code,
            "unchanged": unchanged,
        },
        ensure_ascii=False,
    )
    db.add(
        AuditLog(
            actor_type="system",
            actor_id=(order.user_id if order else None),
            action="ds160.portal.submitted",
            target_type="order",
            target_id=(order.id if order else None),
            payload=payload,
        )
    )


def _load_revoked_codes(order: Order) -> list[str]:
    if not order.ds160_revoked_codes:
        return []
    try:
        revoked = json.loads(order.ds160_revoked_codes)
        return revoked if isinstance(revoked, list) else []
    except (ValueError, TypeError):
        return []


def _is_code_revoked(order: Order, code: str) -> bool:
    if order.ds160_code == code and order.ds160_code_revoked:
        return True
    return code in _load_revoked_codes(order)


async def _lookup_order_by_code(db: AsyncSession, code: str) -> Optional[Order]:
    """Find an order whose active or recently-revoked DS-160 code matches."""
    order = await db.scalar(select(Order).where(Order.ds160_code == code))
    if order is None:
        order = await db.scalar(
            select(Order).where(Order.ds160_revoked_codes.like(f'%"{code}"%'))
        )
    return order


def _client_ip(request: Request) -> str:
    """Honor X-Forwarded-For when present (reverse proxy), fall back to socket."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return (request.client.host if request.client else "unknown")


# --------------------------------------------------------------------------- #
# POST /api/v2/ds160/code                                                      #
# --------------------------------------------------------------------------- #

@router.post(
    "/code",
    response_model=ApiResponse[IssueCodeResponse],
    summary="Issue or refresh a 12-digit DS-160 code for an order (auth required).",
)
async def issue_ds160_code(
    body: IssueCodeRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[IssueCodeResponse]:
    # 1) Auth + ownership
    order = await db.get(Order, body.order_id)
    if order is None:
        raise BizException(ErrorCode.ORDER_NOT_FOUND)
    if order.user_id != current_user.id:
        raise BizException(ErrorCode.FORBIDDEN, message="Not the order owner")
    if order.status not in _ORDER_READY_STATUSES:
        raise BizException(
            ErrorCode.DS160_ORDER_NOT_READY,
            message=f"Order status '{order.status}' does not allow DS-160 code generation",
        )

    # 2) Build profile + fingerprint
    profile = load_applicant_profile(order.applicant_data)
    if not has_minimum_fields(profile):
        raise BizException(
            ErrorCode.DS160_PROFILE_INCOMPLETE,
            message="applicant_data is missing required fields (name / dob / nationality / passport number)",
        )
    fp_new = compute_fingerprint(profile)

    # 3) Idempotent fast path: code still valid, archive unchanged, not revoked.
    # On force_rotate we skip this so the caller always gets a fresh code.
    if (
        not body.force_rotate
        and order.ds160_code
        and order.ds160_fingerprint == fp_new
        and not order.ds160_code_revoked
        and is_valid_code_format(order.ds160_code)
    ):
        _log.info(
            "ds160.code.unchanged order_id=%s code=%s",
            order.id, order.ds160_code,
        )
        return ApiResponse(
            data=IssueCodeResponse(
                order_id=order.id,
                code=order.ds160_code,
                fingerprint=fp_new,
                issued_at=order.ds160_code_issued_at or datetime.utcnow(),
                unchanged=True,
            )
        )

    # 4) Generate a fresh code.  Try a handful of times in the (vanishingly
    # rare) event of collision with another order's code.
    new_code = ""
    for _ in range(8):
        candidate = generate_code()
        exists = await db.scalar(select(Order.id).where(Order.ds160_code == candidate))
        if not exists:
            new_code = candidate
            break
    if not new_code:
        raise BizException(ErrorCode.SERVER_ERROR, message="Code generation exhausted retries")

    # If we're force-rotating, blacklist the previously-active code.  This way
    # the user's old browser/extension tab (still holding the old code) gets a
    # clear 11002 CODE_REVOKED response instead of an opaque ARCHIVE_CHANGED.
    if body.force_rotate and order.ds160_code:
        try:
            revoked = json.loads(order.ds160_revoked_codes or "[]")
            if not isinstance(revoked, list):
                revoked = []
        except (ValueError, TypeError):
            revoked = []
        if order.ds160_code not in revoked:
            revoked.append(order.ds160_code)
        # Cap at 50 most recent revocations to keep the JSON column small.
        order.ds160_revoked_codes = json.dumps(revoked[-50:], ensure_ascii=False)

    order.ds160_code = new_code
    order.ds160_fingerprint = fp_new
    order.ds160_code_issued_at = datetime.utcnow()
    order.ds160_code_consumed_count = 0
    order.ds160_code_revoked = False  # reset for the NEW code; the old code is in revoked_codes list
    await db.commit()
    await db.refresh(order)

    _log.info(
        "ds160.code.issued order_id=%s code=%s unchanged=%s",
        order.id, new_code, False,
    )
    return ApiResponse(
        data=IssueCodeResponse(
            order_id=order.id,
            code=new_code,
            fingerprint=fp_new,
            issued_at=order.ds160_code_issued_at,
            unchanged=False,
        )
    )


# --------------------------------------------------------------------------- #
# POST /api/v2/ds160/code/redeem                                               #
# --------------------------------------------------------------------------- #

@router.post(
    "/code/redeem",
    response_model=ApiResponse[RedeemCodeResponse],
    summary="Exchange a DS-160 code for the applicant's archive (no auth — code is the credential).",
)
async def redeem_ds160_code(
    body: RedeemCodeRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    limiter: Annotated[InMemoryRateLimiter, Depends(get_default_rate_limiter)],
) -> ApiResponse[RedeemCodeResponse]:
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")

    # 1) Format
    code = normalize_code_input(body.code)
    if not is_valid_code_format(code):
        await _audit_redeem(db, order=None, ip=ip, user_agent=ua,
                            success=False, error_code="DS160_CODE_INVALID_FORMAT")
        await db.commit()
        raise BizException(
            ErrorCode.DS160_CODE_INVALID_FORMAT,
            message="Code must be 12 base30 characters (no 0/O/1/I/L/U)",
        )

    # 2) Lookup.  Two places a valid code can hide:
    #      - the order's `ds160_code` column (currently active)
    #      - the order's `ds160_revoked_codes` JSON list (recently rotated away)
    # We do the active lookup first because it's the common case; only on miss
    # do we walk revoked codes.  We use the JSON-encoded shape `["CODE", ...]`
    # with both leading `"` and trailing `"` so we never accidentally match
    # a substring of another code.
    order = await _lookup_order_by_code(db, code)
    if order is None:
        await _audit_redeem(db, order=None, ip=ip, user_agent=ua,
                            success=False, error_code="DS160_CODE_NOT_FOUND")
        await db.commit()
        raise BizException(ErrorCode.DS160_CODE_NOT_FOUND)

    # 3) Rate limit (only after we know it's a real code; pre-lookup rate
    # limit could be bypassed by the format check above)
    allowed, err = limiter.check_and_hit({"order": str(order.id), "ip": ip})
    if not allowed:
        await _audit_redeem(db, order=order, ip=ip, user_agent=ua,
                            success=False, error_code=err)
        await db.commit()
        raise BizException(ErrorCode.RATE_LIMIT, message="Too many redeem attempts")

    # 4) Revoked?
    if _is_code_revoked(order, code):
        await _audit_redeem(db, order=order, ip=ip, user_agent=ua,
                            success=False, error_code="DS160_CODE_REVOKED")
        await db.commit()
        raise BizException(ErrorCode.DS160_CODE_REVOKED)

    # 5) Re-derive fingerprint and compare — THE critical security check.
    profile = load_applicant_profile(order.applicant_data)
    fp_now = compute_fingerprint(profile)
    if order.ds160_fingerprint != fp_now:
        await _audit_redeem(
            db, order=order, ip=ip, user_agent=ua,
            success=False, error_code="DS160_ARCHIVE_CHANGED",
            fingerprint_prefix=fp_now[:8],
        )
        await db.commit()
        raise BizException(
            ErrorCode.DS160_ARCHIVE_CHANGED,
            message="Archive has been updated; fetch a new code from Htex",
            data={
                "hint": "档案已更新, 请回 Htex 拿新 code",
                "issued_fingerprint_prefix": (order.ds160_fingerprint or "")[:8],
                "current_fingerprint_prefix": fp_now[:8],
            },
        )

    # 6) Happy path — bump counters, audit, return profile
    order.ds160_code_consumed_count = (order.ds160_code_consumed_count or 0) + 1
    order.ds160_last_redeemed_at = datetime.utcnow()
    await _audit_redeem(
        db, order=order, ip=ip, user_agent=ua,
        success=True, fingerprint_prefix=fp_now[:8],
    )
    await db.commit()

    _log.info(
        "ds160.code.redeem order_id=%s code=%s fp=%s...",
        order.id, code, fp_now[:8],
    )
    return ApiResponse(
        data=RedeemCodeResponse(
            order_id=order.id,
            profile=profile.to_dict(),
            fingerprint=fp_now,
            mapping_version=DS160_MAPPING_VERSION,
            mapping_verified_date=DS160_MAPPING_VERIFIED_DATE,
            issued_at=order.ds160_code_issued_at or datetime.utcnow(),
        )
    )


# --------------------------------------------------------------------------- #
# POST /api/v2/ds160/portal-submitted                                          #
# --------------------------------------------------------------------------- #

@router.post(
    "/portal-submitted",
    response_model=ApiResponse[PortalSubmittedResponse],
    summary="Record DS-160 portal submission milestone (no auth — code is the credential).",
)
async def mark_ds160_portal_submitted(
    body: RedeemCodeRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PortalSubmittedResponse]:
    """User confirmed they submitted DS-160 on ceac.state.gov.

    This is a **milestone timestamp**, not an order status transition.
    Idempotent: replays return the existing timestamp with unchanged=True.
    No confirmation number or other PII is accepted or stored.
    """
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")

    code = normalize_code_input(body.code)
    if not is_valid_code_format(code):
        await _audit_portal_submitted(
            db, order=None, ip=ip, user_agent=ua,
            success=False, error_code="DS160_CODE_INVALID_FORMAT",
        )
        await db.commit()
        raise BizException(
            ErrorCode.DS160_CODE_INVALID_FORMAT,
            message="Code must be 12 base30 characters (no 0/O/1/I/L/U)",
        )

    order = await _lookup_order_by_code(db, code)
    if order is None:
        await _audit_portal_submitted(
            db, order=None, ip=ip, user_agent=ua,
            success=False, error_code="DS160_CODE_NOT_FOUND",
        )
        await db.commit()
        raise BizException(ErrorCode.DS160_CODE_NOT_FOUND)

    if _is_code_revoked(order, code):
        await _audit_portal_submitted(
            db, order=order, ip=ip, user_agent=ua,
            success=False, error_code="DS160_CODE_REVOKED",
        )
        await db.commit()
        raise BizException(ErrorCode.DS160_CODE_REVOKED)

    if order.status not in _ORDER_READY_STATUSES:
        await _audit_portal_submitted(
            db, order=order, ip=ip, user_agent=ua,
            success=False, error_code="DS160_ORDER_NOT_READY",
        )
        await db.commit()
        raise BizException(
            ErrorCode.DS160_ORDER_NOT_READY,
            message=f"Order status '{order.status}' does not allow portal submission recording",
        )

    if order.portal_submitted_at is not None or order.ds160_portal_submitted_at is not None:
        ts = order.portal_submitted_at or order.ds160_portal_submitted_at
        await _audit_portal_submitted(
            db, order=order, ip=ip, user_agent=ua,
            success=True, unchanged=True,
        )
        await db.commit()
        return ApiResponse(
            data=PortalSubmittedResponse(
                order_id=order.id,
                ds160_portal_submitted_at=ts,
                unchanged=True,
            )
        )

    now = datetime.utcnow()
    order.portal_submitted_at = now
    order.portal_submitted_source = "extension"
    order.ds160_portal_submitted_at = now
    await _audit_portal_submitted(
        db, order=order, ip=ip, user_agent=ua, success=True,
    )
    await db.commit()
    await db.refresh(order)

    _log.info("ds160.portal.submitted order_id=%s code=%s", order.id, code)
    return ApiResponse(
        data=PortalSubmittedResponse(
            order_id=order.id,
            ds160_portal_submitted_at=order.ds160_portal_submitted_at,
            unchanged=False,
        )
    )