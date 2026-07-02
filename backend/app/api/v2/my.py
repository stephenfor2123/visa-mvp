"""
/api/v2/my/applicants — Aggregate distinct applicant names for current user.

Powers the "我的申请" dropdown in AppHeader. Pure read-only aggregation:

  GET /api/v2/my/applicants
    -> { items: [{ id, name, passport_no, order_count, latest_country,
                   latest_status, latest_submitted_at }] }

Behaviour:
  - Scans all orders belonging to the current user (uses idx_orders_user_created).
  - Pulls `applicant_data` JSON out of each order; skips rows where the JSON is
    empty / malformed / missing surname+given_name.
  - Dedupes by (surname, given_name) — same person appearing in N orders shows up
    once, with order_count = N.
  - Each entry shows the most recent order's country/status/submitted_at so the
    user can see "this applicant last applied to US, status submitted" at a glance.

Design notes:
  - No new table. This is a derived view on top of `order.applicant_data`.
  - No write endpoints — applicants are owned by orders, not by users.
  - No click-through behaviour here; the frontend uses this list purely for the
    menu UI. Order detail / one-click-import use the existing /orders endpoints.
"""
import json
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.order import Order
from app.models.user import User
from app.schemas.common import ApiResponse
from pydantic import BaseModel, Field


router = APIRouter(prefix="/my")
_log = get_logger()


# --------------------------------------------------------------------------- #
# Response schemas                                                            #
# --------------------------------------------------------------------------- #
class MyApplicantItem(BaseModel):
    """One distinct applicant (deduped by surname + given_name)."""

    id: str = Field(
        description=(
            "Stable synthetic id derived from the dedup key, e.g. 'app_张三李四'. "
            "Used as Vue list :key only — not a foreign key."
        )
    )
    name: str = Field(description='Display name, e.g. "张三" (surname + given_name)')
    passport_no: Optional[str] = Field(
        default=None, description="Most recent passport_no across the user's orders"
    )
    order_count: int = Field(description="How many orders this applicant appears in")
    latest_country: Optional[str] = Field(
        default=None,
        description="ISO country code from the most recent order's destination",
    )
    latest_status: Optional[str] = Field(
        default=None, description="Most recent order's status"
    )
    latest_submitted_at: Optional[datetime] = Field(
        default=None, description="Most recent order's submitted_at"
    )


class MyApplicantsResponse(BaseModel):
    items: list[MyApplicantItem]


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _safe_parse_applicant(raw: Optional[str]) -> Optional[dict[str, Any]]:
    """Parse order.applicant_data JSON; return None on any failure.

    We are deliberately lenient here — old orders from W13/W14 might have
    JSON in unexpected shapes (e.g. bare string, list of dicts). Anything we
    can't recognise as `{surname, given_name, ...}` we skip silently rather
    than 500 the whole menu.
    """
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _dedup_key(applicant: dict[str, Any]) -> Optional[tuple[str, str]]:
    """Return the dedup key (surname, given_name) lowercased, or None if unusable."""
    surname = (applicant.get("surname") or "").strip()
    given = (applicant.get("given_name") or "").strip()
    if not surname or not given:
        return None
    return (surname, given)


def _display_name(applicant: dict[str, Any]) -> str:
    """Concatenate surname + given_name. Chinese names don't need a separator;
    western names get a single space."""
    surname = (applicant.get("surname") or "").strip()
    given = (applicant.get("given_name") or "").strip()
    # If surname is ASCII (latin letters), add a space; otherwise concatenate.
    if surname and all(ord(c) < 128 for c in surname):
        return f"{surname} {given}"
    return f"{surname}{given}"


# --------------------------------------------------------------------------- #
# GET /my/applicants                                                          #
# --------------------------------------------------------------------------- #
@router.get(
    "/applicants",
    response_model=ApiResponse[MyApplicantsResponse],
    summary="Distinct applicants derived from the current user's orders",
)
async def list_my_applicants(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[MyApplicantsResponse]:
    """Aggregate the current user's orders → distinct (surname, given_name) tuples.

    Returns at most a handful of entries per user (typical 1–5). No pagination
    needed — we cap at 100 orders scanned and 100 applicants returned as a
    safety net; in practice this will be <20.
    """
    # Fetch this user's orders, newest first. We need: applicant_data JSON +
    # destination (country code) + status + submitted_at. The Order model
    # exposes destination_id; resolving the country code requires joining
    # `destinations`. For now, we read destination_id and accept the slight
    # gap — V2.1 will resolve to a real country code via destinations table.
    stmt = (
        select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(desc(Order.created_at))
        .limit(100)
    )
    result = await db.execute(stmt)
    orders: list[Order] = list(result.scalars().all())

    # Group by (surname, given_name); keep the most recent occurrence.
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for order in orders:
        applicant = _safe_parse_applicant(order.applicant_data)
        if not applicant:
            continue
        key = _dedup_key(applicant)
        if not key:
            continue
        if key in by_key:
            # Already have the newest; just bump the count.
            by_key[key]["order_count"] += 1
            continue
        by_key[key] = {
            "name": _display_name(applicant),
            "passport_no": applicant.get("passport_no"),
            "order_count": 1,
            "latest_country": None,  # see TODO note below
            "latest_status": order.status,
            "latest_submitted_at": order.submitted_at,
            "latest_created_at": order.created_at,
        }

    items: list[MyApplicantItem] = []
    for (surname, given), info in by_key.items():
        # Stable synthetic id for Vue :key. We deliberately do NOT use order.id
        # because this entry may span multiple orders.
        item_id = f"app_{surname}_{given}"
        items.append(
            MyApplicantItem(
                id=item_id,
                name=info["name"],
                passport_no=info["passport_no"],
                order_count=info["order_count"],
                latest_country=info["latest_country"],
                latest_status=info["latest_status"],
                latest_submitted_at=info["latest_submitted_at"],
            )
        )

    # Sort by most recent submitted_at desc, then by name for stability.
    items.sort(
        key=lambda x: (
            x.latest_submitted_at or datetime.min,
            x.name,
        ),
        reverse=False,
    )
    items.reverse()  # newest first

    _log.info(
        "my.applicants.list",
        extra={
            "user_id": current_user.id,
            "event_type": "my.applicants.list",
            "status": "success",
            "result_count": len(items),
        },
    )
    return ApiResponse[MyApplicantsResponse](
        code="1000",
        message="OK",
        data=MyApplicantsResponse(items=items),
    )