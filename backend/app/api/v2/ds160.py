"""/api/v2/ds160/* — DS-160 browser extension endpoints.

Security invariants (audit 2026-07 privacy checklist C-01 / E-*):
  - Codes only for paid+ orders (never unpaid ``created``)
  - DB stores SHA-256 hash only; plaintext returned once to the owner
  - Single-use: first successful redeem marks code consumed
  - TTL: 10 minutes from issue
  - Logs never contain the full code (hash prefix only)
  - Refund / revoke clears authorization
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.ds160 import (
    DS160_CODE_TTL_SECONDS,
    InMemoryRateLimiter,
    code_log_prefix,
    compute_fingerprint,
    generate_code,
    get_default_rate_limiter,
    has_minimum_fields,
    hash_code,
    is_valid_code_format,
    load_applicant_profile,
    normalize_code_input,
    revoke_order_ds160,
)
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.audit_log import AuditLog
from app.models.order import Order
from app.models.user import User
from app.schemas.common import ApiResponse


router = APIRouter(prefix="/ds160", tags=["ds160"])
_log = get_logger()

DS160_MAPPING_VERSION = "2026.3"
DS160_MAPPING_VERIFIED_DATE: Optional[str] = None

# C-01 / E-05: plugin auth only after server-confirmed payment (or legacy paid path).
_ORDER_READY_STATUSES = frozenset({
    "paid",
    "completed",
    # legacy post-pay states
    "submitted",
    "reviewing",
    "approved",
})


class IssueCodeRequest(BaseModel):
    order_id: int = Field(..., ge=1)
    force_rotate: bool = Field(
        default=False,
        description="Invalidate the current code and mint a new one.",
    )


class IssueCodeResponse(BaseModel):
    order_id: int
    code: str
    fingerprint: str
    issued_at: datetime
    expires_at: datetime
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _expires_at(issued_at: Optional[datetime]) -> datetime:
    base = issued_at or _utcnow()
    return base + timedelta(seconds=DS160_CODE_TTL_SECONDS)


def _is_code_expired(order: Order) -> bool:
    if order.ds160_code_issued_at is None:
        return True
    return _utcnow() > _expires_at(order.ds160_code_issued_at)


async def _audit_redeem(
    db: AsyncSession,
    *,
    order: Optional[Order],
    ip: str,
    user_agent: str,
    success: bool,
    error_code: str = "",
    fingerprint_prefix: str = "",
    code_prefix: str = "",
) -> None:
    payload = json.dumps(
        {
            "ip": ip,
            "user_agent": user_agent[:200],
            "success": success,
            "error": error_code,
            "fingerprint_prefix": fingerprint_prefix,
            "code_prefix": code_prefix,
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


def _load_revoked_hashes(order: Order) -> list[str]:
    if not order.ds160_revoked_codes:
        return []
    try:
        revoked = json.loads(order.ds160_revoked_codes)
        return revoked if isinstance(revoked, list) else []
    except (ValueError, TypeError):
        return []


def _append_revoked_hash(order: Order, code_hash: str) -> None:
    revoked = _load_revoked_hashes(order)
    if code_hash and code_hash not in revoked:
        revoked.append(code_hash)
    order.ds160_revoked_codes = json.dumps(revoked[-50:], ensure_ascii=False)


def _is_code_revoked(order: Order, code_hash: str) -> bool:
    if order.ds160_code_hash == code_hash and order.ds160_code_revoked:
        return True
    return code_hash in _load_revoked_hashes(order)


def revoke_ds160_authorization(order: Order) -> bool:
    """API-layer alias — invalidate plugin codes (refund / cancel)."""
    return revoke_order_ds160(order)


async def _lookup_order_by_code(db: AsyncSession, code: str) -> Optional[Order]:
    """Find order by code hash (preferred) or legacy plaintext column."""
    digest = hash_code(code)
    order = await db.scalar(select(Order).where(Order.ds160_code_hash == digest))
    if order is not None:
        return order
    # Legacy rows written before hash migration.
    order = await db.scalar(select(Order).where(Order.ds160_code == code))
    if order is not None:
        return order
    # Recently rotated hashes in revoked list.
    order = await db.scalar(
        select(Order).where(Order.ds160_revoked_codes.like(f'%"{digest}"%'))
    )
    return order


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/code",
    response_model=ApiResponse[IssueCodeResponse],
    summary="Issue or refresh a 12-digit DS-160 code for a paid order (auth required).",
)
async def issue_ds160_code(
    body: IssueCodeRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[IssueCodeResponse]:
    order = await db.get(Order, body.order_id)
    if order is None:
        raise BizException(ErrorCode.ORDER_NOT_FOUND)
    if order.user_id != current_user.id:
        raise BizException(ErrorCode.FORBIDDEN, message="Not the order owner")
    if order.status not in _ORDER_READY_STATUSES:
        raise BizException(
            ErrorCode.DS160_ORDER_NOT_READY,
            message=f"Order status '{order.status}' does not allow DS-160 code generation (payment required)",
        )

    profile = load_applicant_profile(order.applicant_data)
    if not has_minimum_fields(profile):
        raise BizException(
            ErrorCode.DS160_PROFILE_INCOMPLETE,
            message="applicant_data is missing required fields (name / dob / nationality / passport number)",
        )
    fp_new = compute_fingerprint(profile)

    # Plaintext is never stored. Any re-issue rotates the previous hash.
    if order.ds160_code_hash:
        _append_revoked_hash(order, order.ds160_code_hash)

    new_code = ""
    for _ in range(8):
        candidate = generate_code()
        digest = hash_code(candidate)
        exists = await db.scalar(
            select(Order.id).where(
                or_(
                    Order.ds160_code_hash == digest,
                    Order.ds160_code == candidate,
                )
            )
        )
        if not exists:
            new_code = candidate
            break
    if not new_code:
        raise BizException(ErrorCode.SERVER_ERROR, message="Code generation exhausted retries")

    digest = hash_code(new_code)
    issued_at = _utcnow()
    order.ds160_code = None  # never persist plaintext
    order.ds160_code_hash = digest
    order.ds160_fingerprint = fp_new
    order.ds160_code_issued_at = issued_at
    order.ds160_code_consumed_count = 0
    order.ds160_code_revoked = False
    await db.commit()
    await db.refresh(order)

    _log.info(
        "ds160.code.issued order_id={} code_prefix={}",
        order.id,
        code_log_prefix(digest),
    )
    return ApiResponse(
        data=IssueCodeResponse(
            order_id=order.id,
            code=new_code,
            fingerprint=fp_new,
            issued_at=issued_at,
            expires_at=_expires_at(issued_at),
            unchanged=False,
        )
    )


@router.post(
    "/code/redeem",
    response_model=ApiResponse[RedeemCodeResponse],
    summary="Exchange a DS-160 code for the applicant archive (code is the credential).",
)
async def redeem_ds160_code(
    body: RedeemCodeRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    limiter: Annotated[InMemoryRateLimiter, Depends(get_default_rate_limiter)],
) -> ApiResponse[RedeemCodeResponse]:
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")
    code_prefix = ""

    code = normalize_code_input(body.code)
    if not is_valid_code_format(code):
        await _audit_redeem(
            db, order=None, ip=ip, user_agent=ua,
            success=False, error_code="DS160_CODE_INVALID_FORMAT",
        )
        await db.commit()
        raise BizException(
            ErrorCode.DS160_CODE_INVALID_FORMAT,
            message="Code must be 12 base30 characters (no 0/O/1/I/L/U)",
        )

    code_prefix = code_log_prefix(code)
    order = await _lookup_order_by_code(db, code)
    if order is None:
        await _audit_redeem(
            db, order=None, ip=ip, user_agent=ua,
            success=False, error_code="DS160_CODE_NOT_FOUND", code_prefix=code_prefix,
        )
        await db.commit()
        raise BizException(ErrorCode.DS160_CODE_NOT_FOUND)

    digest = hash_code(code)

    allowed, err = limiter.check_and_hit({"order": str(order.id), "ip": ip})
    if not allowed:
        await _audit_redeem(
            db, order=order, ip=ip, user_agent=ua,
            success=False, error_code=err, code_prefix=code_prefix,
        )
        await db.commit()
        raise BizException(ErrorCode.RATE_LIMIT, message="Too many redeem attempts")

    if order.status not in _ORDER_READY_STATUSES:
        await _audit_redeem(
            db, order=order, ip=ip, user_agent=ua,
            success=False, error_code="DS160_ORDER_NOT_READY", code_prefix=code_prefix,
        )
        await db.commit()
        raise BizException(
            ErrorCode.DS160_ORDER_NOT_READY,
            message="Order is not paid; plugin authorization denied",
        )

    if _is_code_revoked(order, digest):
        await _audit_redeem(
            db, order=order, ip=ip, user_agent=ua,
            success=False, error_code="DS160_CODE_REVOKED", code_prefix=code_prefix,
        )
        await db.commit()
        raise BizException(ErrorCode.DS160_CODE_REVOKED)

    if (order.ds160_code_consumed_count or 0) >= 1:
        await _audit_redeem(
            db, order=order, ip=ip, user_agent=ua,
            success=False, error_code="DS160_CODE_USED", code_prefix=code_prefix,
        )
        await db.commit()
        raise BizException(ErrorCode.DS160_CODE_USED, message="Code already used")

    if _is_code_expired(order):
        await _audit_redeem(
            db, order=order, ip=ip, user_agent=ua,
            success=False, error_code="DS160_CODE_EXPIRED", code_prefix=code_prefix,
        )
        await db.commit()
        raise BizException(ErrorCode.DS160_CODE_EXPIRED, message="Code has expired")

    profile = load_applicant_profile(order.applicant_data)
    fp_now = compute_fingerprint(profile)
    if order.ds160_fingerprint != fp_now:
        await _audit_redeem(
            db, order=order, ip=ip, user_agent=ua,
            success=False, error_code="DS160_ARCHIVE_CHANGED",
            fingerprint_prefix=fp_now[:8], code_prefix=code_prefix,
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

    # Single-use consume
    order.ds160_code_consumed_count = (order.ds160_code_consumed_count or 0) + 1
    order.ds160_last_redeemed_at = _utcnow()
    order.ds160_code_revoked = True
    if order.ds160_code_hash:
        _append_revoked_hash(order, order.ds160_code_hash)
    order.ds160_code = None

    await _audit_redeem(
        db, order=order, ip=ip, user_agent=ua,
        success=True, fingerprint_prefix=fp_now[:8], code_prefix=code_prefix,
    )
    await db.commit()

    _log.info(
        "ds160.code.redeem order_id={} code_prefix={} fp={}...",
        order.id, code_prefix, fp_now[:8],
    )
    return ApiResponse(
        data=RedeemCodeResponse(
            order_id=order.id,
            profile=profile.to_dict(),
            fingerprint=fp_now,
            mapping_version=DS160_MAPPING_VERSION,
            mapping_verified_date=DS160_MAPPING_VERIFIED_DATE,
            issued_at=order.ds160_code_issued_at or _utcnow(),
        )
    )


@router.post(
    "/portal-submitted",
    response_model=ApiResponse[PortalSubmittedResponse],
    summary="Record DS-160 portal submission milestone (code is the credential).",
)
async def mark_ds160_portal_submitted(
    body: RedeemCodeRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PortalSubmittedResponse]:
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

    digest = hash_code(code)
    if _is_code_revoked(order, digest) and (order.ds160_code_consumed_count or 0) == 0:
        # Allow portal-submitted after a successful redeem (code is revoked-as-used).
        if not order.ds160_last_redeemed_at:
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

    now = _utcnow()
    order.portal_submitted_at = now
    order.portal_submitted_source = "extension"
    order.ds160_portal_submitted_at = now
    await _audit_portal_submitted(
        db, order=order, ip=ip, user_agent=ua, success=True,
    )
    await db.commit()
    await db.refresh(order)

    _log.info(
        "ds160.portal.submitted order_id={} code_prefix={}",
        order.id, code_log_prefix(code),
    )
    return ApiResponse(
        data=PortalSubmittedResponse(
            order_id=order.id,
            ds160_portal_submitted_at=order.ds160_portal_submitted_at,
            unchanged=False,
        )
    )
