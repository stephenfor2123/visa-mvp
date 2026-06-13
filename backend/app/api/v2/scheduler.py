"""/scheduler/* — V2 §4.2.4 internal scheduler endpoints.

These endpoints are NOT under `/api/v2` and do NOT accept user JWTs.
They authenticate via a shared-secret header `X-System-Key` (env var
`SYSTEM_API_KEY`). The intent is that only the internal cron / Celery
beat / k8s CronJob can invoke them.

Endpoints this Story adds:
  - POST /scheduler/poll-tick    run one bulk status poll against all
                                  in-flight orders (status IN submitted,
                                  reviewing) and advance them per the
                                  RPA stub rules.
"""
from __future__ import annotations

import secrets
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.schemas.common import ApiResponse
from app.services.poll_service import PollService


router = APIRouter()
_log = get_logger()


# --------------------------------------------------------------------------- #
# System-key dependency                                                       #
# --------------------------------------------------------------------------- #
async def require_system_key(
    x_system_key: Annotated[
        Optional[str],
        Header(
            alias="X-System-Key",
            description="Shared secret from SYSTEM_API_KEY env var",
        ),
    ] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """Verify the `X-System-Key` header matches the configured secret.

    Uses a constant-time comparison so the endpoint can't be timed-attacked.

    Returns 401 UNAUTHORIZED (code 1005) on:
      - missing header
      - malformed header (wrong type after validation, rare)
      - value mismatch
    """
    if not x_system_key:
        raise BizException(
            ErrorCode.UNAUTHORIZED,
            message="Missing X-System-Key header",
            data={"hint": "internal endpoint, requires SYSTEM_API_KEY"},
        )
    if not secrets.compare_digest(x_system_key, settings.system_api_key):
        raise BizException(
            ErrorCode.UNAUTHORIZED,
            message="Invalid X-System-Key",
            data={},
        )


# --------------------------------------------------------------------------- #
# POST /scheduler/poll-tick                                                   #
# --------------------------------------------------------------------------- #
@router.post(
    "/poll-tick",
    response_model=ApiResponse[dict],
    summary=(
        "Walk all in-flight orders, ask the RPA stub for status updates, "
        "and persist any state changes. System-key auth only."
    ),
)
async def poll_tick(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_system_key)],
) -> ApiResponse[dict]:
    """One bulk poll-tick.

    Response payload (under `data`):
      {
        "ticked":  <int>,                # orders inspected
        "changed": <int>,                # orders that actually transitioned
        "logs":    [<poll-log dict>, ...]
      }

    Notes:
      * No request body required; everything is server-driven.
      * Idempotent at the level of "we'll re-poll the same orders next
        time" — RPA is allowed to return "no change" repeatedly.
      * `logs` only contains state-CHANGE rows (no-change rows are NOT
        recorded, per Story 1.2.2a spec).
    """
    service = PollService(db)
    result = await service.tick(poll_source="scheduler_tick")
    _log.info(
        "poll-tick HTTP response ticked={} changed={}",
        result["ticked"],
        result["changed"],
    )
    return ApiResponse[dict](code="1000", message="OK", data=result)