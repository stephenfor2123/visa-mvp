"""POST /api/v2/analytics/track — client product 埋点 (anonymous OK)."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import BizException, ErrorCode
from app.core.security import (
    TOKEN_TYPE_ACCESS,
    assert_token_valid_for_user,
    decode_token,
)
from app.models.user import User
from app.schemas.analytics import TrackEventData, TrackEventRequest
from app.schemas.common import ApiResponse
from app.services.analytics import ALLOWED_CLIENT_EVENTS, record_event

router = APIRouter()
_optional_bearer = HTTPBearer(auto_error=False)


async def get_optional_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(_optional_bearer)
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Resolve JWT when present; anonymous callers get None (no 401)."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = decode_token(credentials.credentials, TOKEN_TYPE_ACCESS)
        user_id = int(payload["sub"])
    except Exception:  # noqa: BLE001 — bad/expired token → treat as anonymous
        return None
    user = await db.get(User, user_id)
    if user is None or user.status != "active":
        return None
    try:
        assert_token_valid_for_user(payload, user)
    except Exception:  # noqa: BLE001
        return None
    return user


@router.post(
    "/track",
    response_model=ApiResponse[TrackEventData],
    summary="Record a client analytics event (fire-and-forget)",
)
async def track_event(
    body: TrackEventRequest,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> ApiResponse[TrackEventData]:
    name = (body.event or "").strip()
    if name not in ALLOWED_CLIENT_EVENTS:
        raise BizException(
            ErrorCode.INVALID_PARAMS,
            message=f"Unknown analytics event: {name}",
            data={"allowed": sorted(ALLOWED_CLIENT_EVENTS)},
        )

    props = dict(body.props or {})
    # Prefer top-level denorm fields; fall back to props
    country = body.country_code or props.get("country_code")
    order_no = body.order_no or props.get("order_no")
    path = body.path or props.get("path")

    event_id = await record_event(
        db,
        event_name=name,
        user_id=user.id if user else None,
        session_id=body.session_id,
        country_code=country,
        order_no=order_no,
        props=props or None,
        source="client",
        path=path,
        commit=True,
    )
    return ApiResponse(
        data=TrackEventData(
            event_id=event_id,
            event=name,
            tracked_at=datetime.utcnow(),
        )
    )
