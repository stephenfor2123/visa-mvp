"""Admin cleanup router — V2 §4.1.4 / §4.3.5 / §4.7.

端点 (全部需要 verify_admin_token):
  - GET  /api/v2/admin/cleanup/stats
  - POST /api/v2/admin/cleanup/temp-files
  - POST /api/v2/admin/cleanup/archived-files
  - POST /api/v2/admin/cleanup/pending-destroys

设计:
  - 路由前缀 /api/v2/admin/cleanup (由 __init__.py 挂载到 admin 子 router 下)
  - 复用 AdminService 的 audit 模式 (record_audit 由 CleanupService 内部调用)
  - 返回 schema: ApiResponse[CleanupStatsOut] / ApiResponse[CleanupResultOut]
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.middleware.admin_auth import verify_admin_token
from app.schemas.admin import (
    AdminTokenData,
    CleanupResultOut,
    CleanupStatsOut,
)
from app.schemas.common import ApiResponse
from app.services.cleanup_service import CleanupService


_log = get_logger()
router = APIRouter(prefix="/admin/cleanup", tags=["admin-cleanup"])


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get(
    "/stats",
    response_model=ApiResponse[CleanupStatsOut],
    summary="Get cleanup candidate counts (V2 §4.1.4 / §4.3.5)",
)
async def get_cleanup_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[CleanupStatsOut]:
    svc = CleanupService(db)
    stats = await svc.get_stats()
    return ApiResponse[CleanupStatsOut](
        code="1000", message="OK",
        data=CleanupStatsOut(**stats),
    )


@router.post(
    "/temp-files",
    response_model=ApiResponse[CleanupResultOut],
    summary="Manually trigger temp file cleanup (>24h)",
)
async def cleanup_temp_files(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[CleanupResultOut]:
    svc = CleanupService(db)
    result = await svc.cleanup_temp_files(
        actor_type="admin", actor_id=admin.admin_id,
    )
    return ApiResponse[CleanupResultOut](
        code="1000", message="OK",
        data=CleanupResultOut(
            action="temp_files",
            deleted_count=result["deleted_count"],
            freed_bytes=result["freed_bytes"],
            duration_ms=result["duration_ms"],
            affected_users=[],
            finished_at=_now_naive(),
            errors=result["errors"],
        ),
    )


@router.post(
    "/archived-files",
    response_model=ApiResponse[CleanupResultOut],
    summary="Manually trigger archived file cleanup (>180h)",
)
async def cleanup_archived_files(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[CleanupResultOut]:
    svc = CleanupService(db)
    result = await svc.cleanup_archived_files(
        actor_type="admin", actor_id=admin.admin_id,
    )
    return ApiResponse[CleanupResultOut](
        code="1000", message="OK",
        data=CleanupResultOut(
            action="archived_files",
            deleted_count=result["deleted_count"],
            freed_bytes=result["freed_bytes"],
            duration_ms=result["duration_ms"],
            affected_users=[],
            finished_at=_now_naive(),
            errors=result["errors"],
        ),
    )


@router.post(
    "/pending-destroys",
    response_model=ApiResponse[CleanupResultOut],
    summary="Manually trigger 72h account destroy cleanup",
)
async def cleanup_pending_destroys(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[CleanupResultOut]:
    svc = CleanupService(db)
    result = await svc.run_pending_destroy_users(
        actor_type="admin", actor_id=admin.admin_id,
    )
    return ApiResponse[CleanupResultOut](
        code="1000", message="OK",
        data=CleanupResultOut(
            action="pending_destroys",
            deleted_count=result["deleted_count"],
            freed_bytes=result["freed_bytes"],
            duration_ms=result["duration_ms"],
            affected_users=result["affected_users"],
            finished_at=_now_naive(),
            errors=result["errors"],
        ),
    )