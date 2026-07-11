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
from app.services.rag.refresh import (
    cleanup_expired_snapshots,
    refresh_all,
)


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

    Disabled when ``feature_rpa_enabled`` is false.
    """
    if not get_settings().feature_rpa_enabled:
        return ApiResponse[dict](
            code="1000",
            message="RPA disabled (feature_rpa_enabled=false)",
            data={"ticked": 0, "changed": 0, "logs": [], "rpa_enabled": False},
        )
    service = PollService(db)
    result = await service.tick(poll_source="scheduler_tick")
    _log.info(
        "poll-tick HTTP response ticked={} changed={}",
        result["ticked"],
        result["changed"],
    )
    return ApiResponse[dict](code="1000", message="OK", data=result)


# --------------------------------------------------------------------------- #
# POST /scheduler/rag-refresh-tick                                             #
# --------------------------------------------------------------------------- #
@router.post(
    "/rag-refresh-tick",
    response_model=ApiResponse[dict],
    summary=(
        "Walk all enabled RAG sources, fetch + chunk + write review snapshot. "
        "System-key auth only."
    ),
)
async def rag_refresh_tick(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_system_key)],
    country_code: Annotated[Optional[str], "Filter by ISO country code"] = None,
) -> ApiResponse[dict]:
    """One RAG refresh-tick.

    调用 refresh_all(mode='review') — 抓完存 RagReviewSnapshot,不直接覆盖 RagChunk。
    admin 在 /admin/rag-review 看到 pending_review 的 snapshot 决定 approve/reject。

    同时跑 cleanup_expired_snapshots 清理 7 天前的 auto-expired snapshot。

    Response payload (under `data`):
      {
        "refreshed":  <int>,        # sources that fetched OK
        "errors":     <int>,        # sources that errored
        "content_changed": <int>,   # sources whose content hash actually changed
        "snapshots_created": <int>, # 写入的 snapshot 数量
        "snapshots_expired": <int>, # 这次清理掉的过期 snapshot
        "items":      [<per-source dict>, ...]
      }

    设计上每 6h 跑一次 (k8s CronJob: 0 */6 * * *)。已 pending_review 的
    source 不会重复刷新 (refresh_source 会 expire 旧 snapshot 再建新的)。
    """
    # 先清理过期 snapshot
    expired = await cleanup_expired_snapshots(db)
    # 再跑一轮 refresh
    items = await refresh_all(db, country_code=country_code, mode="review")
    refreshed = sum(1 for x in items if x.get("status") == "ok")
    errors = sum(1 for x in items if x.get("status") == "error")
    content_changed = sum(1 for x in items if x.get("content_changed"))
    snapshots_created = sum(1 for x in items if x.get("snapshot_id"))
    _log.info(
        "rag-refresh-tick refreshed={} errors={} changed={} new_snapshots={} expired={}",
        refreshed, errors, content_changed, snapshots_created, expired,
    )
    return ApiResponse[dict](code="1000", message="OK", data={
        "refreshed": refreshed,
        "errors": errors,
        "content_changed": content_changed,
        "snapshots_created": snapshots_created,
        "snapshots_expired": expired,
        "items": items,
    })