"""Admin cleanup router — V2 §4.1.4 / §4.3.5 / §4.7.

端点 (全部需要 verify_admin_token):
  - GET  /api/v2/admin/cleanup/stats
  - POST /api/v2/admin/cleanup/temp-files       # 2026-07-07 保留兼容, 内部仍可调
  - POST /api/v2/admin/cleanup/archived-files   # 2026-07-07 保留兼容, 内部仍可调
  - POST /api/v2/admin/cleanup/cache-files      # 2026-07-07: 合并 temp + archived, 前端默认走这个
  - POST /api/v2/admin/cleanup/pending-destroys

设计:
  - 路由前缀 /api/v2/admin/cleanup (由 __init__.py 挂载到 admin 子 router 下)
  - 复用 AdminService 的 audit 模式 (record_audit 由 CleanupService 内部调用)
  - 返回 schema: ApiResponse[CleanupStatsOut] / ApiResponse[CleanupResultOut]
"""
from datetime import datetime, timezone
import time
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.middleware.admin_auth import verify_admin_token, verify_admin_token_with_db, require_perm
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
    dependencies=[Depends(require_perm("system.cleanup"))],
    response_model=ApiResponse[CleanupStatsOut],
    summary="Get cleanup candidate counts (V2 §4.1.4 / §4.3.5)",
)
async def get_cleanup_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[CleanupStatsOut]:
    svc = CleanupService(db)
    stats = await svc.get_stats()
    return ApiResponse[CleanupStatsOut](
        code="1000", message="OK",
        data=CleanupStatsOut(**stats),
    )


@router.post(
    "/temp-files",
    dependencies=[Depends(require_perm("system.cleanup"))],
    response_model=ApiResponse[CleanupResultOut],
    summary="Manually trigger temp file cleanup (>24h)",
)
async def cleanup_temp_files(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
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
    dependencies=[Depends(require_perm("system.cleanup"))],
    response_model=ApiResponse[CleanupResultOut],
    summary="Manually trigger archived file cleanup (>180h)",
)
async def cleanup_archived_files(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
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
    "/cache-files",
    dependencies=[Depends(require_perm("system.cleanup"))],
    response_model=ApiResponse[CleanupResultOut],
    summary="Manually trigger combined cache file cleanup (temp + archived)",
)
async def cleanup_cache_files(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[CleanupResultOut]:
    """2026-07-07: 前端合并按钮走的端点, 一次性跑 temp + archived 两个清理。"""
    svc = CleanupService(db)
    t0 = time.monotonic()
    errors: list[str] = []
    total_deleted = 0
    total_freed = 0
    affected_users: list[int] = []

    # 1) 临时文件
    r1 = await svc.cleanup_temp_files(actor_type="admin", actor_id=admin.admin_id)
    total_deleted += r1["deleted_count"]
    total_freed += r1["freed_bytes"]
    errors.extend(r1["errors"])

    # 2) 归档文件
    r2 = await svc.cleanup_archived_files(actor_type="admin", actor_id=admin.admin_id)
    total_deleted += r2["deleted_count"]
    total_freed += r2["freed_bytes"]
    errors.extend(r2["errors"])

    duration_ms = int((time.monotonic() - t0) * 1000)
    return ApiResponse[CleanupResultOut](
        code="1000", message="OK",
        data=CleanupResultOut(
            action="cache_files",
            deleted_count=total_deleted,
            freed_bytes=total_freed,
            duration_ms=duration_ms,
            affected_users=affected_users,
            finished_at=_now_naive(),
            errors=errors,
        ),
    )


@router.post(
    "/pending-destroys",
    dependencies=[Depends(require_perm("system.cleanup"))],
    response_model=ApiResponse[CleanupResultOut],
    summary="Manually trigger 72h account destroy cleanup",
)
async def cleanup_pending_destroys(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
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