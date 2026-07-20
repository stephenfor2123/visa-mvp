"""Product analytics helpers — append-only event writes."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.analytics_event import AnalyticsEvent

_log = get_logger()

# Canonical event names (keep FE + BE aligned)
EVENT_PAGE_VIEW = "page_view"
EVENT_COUNTRY_SELECTED = "country_selected"
EVENT_WIZARD_STARTED = "wizard_started"
EVENT_FORM_COMPLETED = "form_completed"
EVENT_LOGIN_WALL_SHOWN = "login_wall_shown"
EVENT_AUTH_SUCCEEDED = "auth_succeeded"
EVENT_ORDER_CREATED = "order_created"
EVENT_CHECKOUT_VIEWED = "checkout_viewed"
EVENT_CHECKOUT_STARTED = "checkout_started"
EVENT_PAYMENT_SUCCEEDED = "payment_succeeded"
EVENT_PAYMENT_FAILED = "payment_failed"
EVENT_ORDER_DETAIL_VIEWED = "order_detail_viewed"
EVENT_ORDER_COMPLETED = "order_completed"

ALLOWED_CLIENT_EVENTS = frozenset({
    EVENT_PAGE_VIEW,
    EVENT_COUNTRY_SELECTED,
    EVENT_WIZARD_STARTED,
    EVENT_FORM_COMPLETED,
    EVENT_LOGIN_WALL_SHOWN,
    EVENT_AUTH_SUCCEEDED,
    EVENT_CHECKOUT_VIEWED,
    EVENT_CHECKOUT_STARTED,
    EVENT_ORDER_DETAIL_VIEWED,
    # Client may also echo server milestones for UX timing (dedupe via source)
    EVENT_ORDER_CREATED,
    EVENT_PAYMENT_SUCCEEDED,
    EVENT_PAYMENT_FAILED,
})


async def record_event(
    db: AsyncSession,
    *,
    event_name: str,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    country_code: Optional[str] = None,
    order_no: Optional[str] = None,
    props: Optional[dict[str, Any]] = None,
    source: str = "server",
    path: Optional[str] = None,
    commit: bool = False,
) -> int:
    """Insert an analytics row. Caller commits unless commit=True."""
    row = AnalyticsEvent(
        event_name=event_name[:64],
        user_id=user_id,
        session_id=(session_id or None) and str(session_id)[:64],
        country_code=(country_code or None) and str(country_code).upper()[:8],
        order_no=(order_no or None) and str(order_no)[:32],
        props=json.dumps(props, ensure_ascii=False) if props else None,
        source=(source or "server")[:16],
        path=(path or None) and str(path)[:255],
    )
    db.add(row)
    await db.flush()
    if commit:
        await db.commit()
    _log.info(
        "analytics event={} source={} user_id={} order_no={}",
        event_name,
        source,
        user_id,
        order_no,
    )
    return row.id


async def record_event_safe(
    db: AsyncSession,
    **kwargs: Any,
) -> Optional[int]:
    """Best-effort write — never raises into the caller."""
    try:
        return await record_event(db, **kwargs)
    except Exception as exc:  # noqa: BLE001 — defensive
        _log.warning("analytics record_event_safe swallowed: {}", exc)
        return None
