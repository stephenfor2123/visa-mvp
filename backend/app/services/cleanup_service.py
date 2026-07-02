"""CleanupService — V2 §4.1.4 (72h 用户注销清理) + §4.3.5 (临时/归档文件清理).

职责:
  - cleanup_temp_files()    : 删除 24h 前的临时文件 (storage_key 含 "tmp" 或 "temp")
  - cleanup_archived_files() : 删除 180h 前的归档文件 (archived=true 且超过保留期)
  - cleanup_user_data(user_id): 清空某用户的订单/材料/物理文件,保留 audit_log
  - run_pending_destroy_users(): 扫描 status=pending_destroy 且 updated_at > 72h 的用户,
                                  对每用户执行 cleanup_user_data + status=destroyed
  - get_stats()              : 当前可清理量 + 上次执行时间 (供 dashboard 展示)

实现要点:
  - 物理文件删除前必须先 record_audit 留痕 (即使后面删除失败也能追溯)
  - 数据库操作走当前 AsyncSession,commit 由调用方负责
  - 单条物理删除失败不阻断后续 — 错误聚合到 errors[],最后 commit 一次
  - run_pending_destroy_users 用 72h 阈值 (V2 §4.1.4)
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.material import Material
from app.models.order import Order, OrderStatusHistory
from app.models.user import User
from app.services import storage
from app.services.audit import record_audit


_log = get_logger()


# --------------------------------------------------------------------------- #
# 配置常量                                                                    #
# --------------------------------------------------------------------------- #
TEMP_FILE_MAX_AGE_HOURS = 24       # V2 §4.3.5
ARCHIVE_FILE_MAX_AGE_HOURS = 180   # V2 §4.3.5
PENDING_DESTROY_MAX_AGE_HOURS = 72 # V2 §4.1.4


def _utcnow_naive() -> datetime:
    """与 SQLAlchemy `DateTime` 列一致 (naive UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _human_bytes(n: int) -> str:
    """格式化字节数 (debug 日志用)."""
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f}KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024*1024):.1f}MB"
    return f"{n / (1024*1024*1024):.2f}GB"


class CleanupService:
    """文件清理 + 用户注销执行器."""

    # 模块级缓存 (跨实例): 上次自动调度执行时间,供 stats 展示
    _last_run_at: Optional[datetime] = None

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ====================================================================== #
    # 1) 临时文件清理 (24h, storage_key 含 'tmp' 或 'temp')                     #
    # ====================================================================== #
    async def cleanup_temp_files(
        self, *, actor_type: str = "system", actor_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """删除超过 24h 的临时文件. 命中条件: storage_key 含 'tmp' 或 'temp'.

        Returns: dict with deleted_count, freed_bytes, duration_ms, errors[]
        """
        start = time.monotonic()
        cutoff = _utcnow_naive() - timedelta(hours=TEMP_FILE_MAX_AGE_HOURS)

        # 1) 找出候选 (按 created_at < cutoff 且 storage_key 命中关键词)
        stmt = select(Material).where(
            Material.deleted_at.is_(None),
            Material.created_at < cutoff,
            (
                Material.storage_key.like("%/tmp/%")
                | Material.storage_key.like("%tmp_%")
                | Material.storage_key.like("%/temp/%")
                | Material.storage_key.like("%temp_%")
                | Material.storage_key.like("tmp/%")
                | Material.storage_key.like("temp/%")
            ),
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        deleted_count = 0
        freed_bytes = 0
        errors: list[str] = []

        for row in rows:
            # 2) audit 留痕 (必须在物理删除之前)
            try:
                await record_audit(
                    self.db,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action="cleanup.temp_file.delete",
                    target_type="material",
                    target_id=row.id,
                    payload={
                        "storage_key": row.storage_key,
                        "file_size": row.file_size,
                        "age_hours": int((_utcnow_naive() - row.created_at).total_seconds() / 3600),
                        "reason": f"temp_file_>{TEMP_FILE_MAX_AGE_HOURS}h",
                    },
                )
            except Exception as exc:
                _log.warning("audit write failed for material {}: {}", row.id, exc)
                errors.append(f"audit[{row.id}]: {exc}")

            # 3) 物理删除文件
            try:
                abs_path = storage.path_for(row.storage_key)
                if abs_path.exists():
                    abs_path.unlink()
                    freed_bytes += row.file_size
            except Exception as exc:
                _log.warning("physical delete failed for {}: {}", row.storage_key, exc)
                errors.append(f"file[{row.id}]: {exc}")
                # 即使物理失败也标记 DB 删除 (DB 记录是 single source of truth)

            # 4) 软删 DB 行 (deleted_at + archived)
            row.deleted_at = _utcnow_naive()
            deleted_count += 1

        await self.db.commit()
        CleanupService._last_run_at = _utcnow_naive()

        duration_ms = int((time.monotonic() - start) * 1000)
        _log.info(
            "cleanup_temp_files: deleted={} freed={} errors={} duration={}ms",
            deleted_count, _human_bytes(freed_bytes), len(errors), duration_ms,
        )
        return {
            "deleted_count": deleted_count,
            "freed_bytes": freed_bytes,
            "duration_ms": duration_ms,
            "errors": errors,
        }

    # ====================================================================== #
    # 2) 归档文件清理 (180h, archived=true 或 storage_key 含 'archive')        #
    # ====================================================================== #
    async def cleanup_archived_files(
        self, *, actor_type: str = "system", actor_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """删除 180h 前的归档文件.

        命中条件 (满足任一):
          - archived=True 且 created_at < cutoff (180h)
          - storage_key 含 '/archive/' 或 'archive_' 关键词
        """
        start = time.monotonic()
        cutoff = _utcnow_naive() - timedelta(hours=ARCHIVE_FILE_MAX_AGE_HOURS)

        stmt = select(Material).where(
            Material.deleted_at.is_(None),
            Material.created_at < cutoff,
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        deleted_count = 0
        freed_bytes = 0
        errors: list[str] = []

        for row in rows:
            is_archived = bool(row.archived) or ("archive" in (row.storage_key or "").lower())
            if not is_archived:
                continue

            try:
                await record_audit(
                    self.db,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action="cleanup.archived_file.delete",
                    target_type="material",
                    target_id=row.id,
                    payload={
                        "storage_key": row.storage_key,
                        "file_size": row.file_size,
                        "archived": row.archived,
                        "age_hours": int((_utcnow_naive() - row.created_at).total_seconds() / 3600),
                        "reason": f"archived_>{ARCHIVE_FILE_MAX_AGE_HOURS}h",
                    },
                )
            except Exception as exc:
                _log.warning("audit write failed for material {}: {}", row.id, exc)
                errors.append(f"audit[{row.id}]: {exc}")

            try:
                abs_path = storage.path_for(row.storage_key)
                if abs_path.exists():
                    abs_path.unlink()
                    freed_bytes += row.file_size
            except Exception as exc:
                _log.warning("physical delete failed for {}: {}", row.storage_key, exc)
                errors.append(f"file[{row.id}]: {exc}")

            row.deleted_at = _utcnow_naive()
            deleted_count += 1

        await self.db.commit()
        CleanupService._last_run_at = _utcnow_naive()

        duration_ms = int((time.monotonic() - start) * 1000)
        _log.info(
            "cleanup_archived_files: deleted={} freed={} errors={} duration={}ms",
            deleted_count, _human_bytes(freed_bytes), len(errors), duration_ms,
        )
        return {
            "deleted_count": deleted_count,
            "freed_bytes": freed_bytes,
            "duration_ms": duration_ms,
            "errors": errors,
        }

    # ====================================================================== #
    # 3) 单用户数据清理 (72h 注销流程的内部步骤)                                #
    # ====================================================================== #
    async def cleanup_user_data(
        self,
        user_id: int,
        *,
        actor_type: str = "system",
        actor_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """清空某用户的所有材料物理文件 + 软删订单,保留 audit_log.

        Steps:
          1. 找出该用户所有 alive materials
          2. 每条: 物理删除 + soft delete
          3. 找出该用户所有 orders, 在 audit 里写一条 user.destroy, 不物理删 orders
             (保留订单记录供资金流追溯,只清空 applicant_data / material_ids 关联)
        """
        start = time.monotonic()
        deleted_materials = 0
        freed_bytes = 0
        affected_orders = 0
        errors: list[str] = []

        # 1) 该用户的 alive materials
        m_rows = (await self.db.execute(
            select(Material).where(
                Material.user_id == user_id,
                Material.deleted_at.is_(None),
            )
        )).scalars().all()

        for row in m_rows:
            try:
                await record_audit(
                    self.db,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action="cleanup.user_destroy.material",
                    target_type="material",
                    target_id=row.id,
                    payload={
                        "user_id": user_id,
                        "storage_key": row.storage_key,
                        "file_size": row.file_size,
                    },
                )
            except Exception as exc:
                _log.warning("audit write failed for material {}: {}", row.id, exc)
                errors.append(f"audit[mat:{row.id}]: {exc}")

            try:
                abs_path = storage.path_for(row.storage_key)
                if abs_path.exists():
                    abs_path.unlink()
                    freed_bytes += row.file_size
            except Exception as exc:
                _log.warning("physical delete failed for {}: {}", row.storage_key, exc)
                errors.append(f"file[mat:{row.id}]: {exc}")

            row.deleted_at = _utcnow_naive()
            deleted_materials += 1

        # 2) 该用户的 orders — 清空 applicant_data (PII), 保留行供审计
        o_rows = (await self.db.execute(
            select(Order).where(Order.user_id == user_id)
        )).scalars().all()
        for order in o_rows:
            order.applicant_data = None
            order.material_ids = None
            order.destination_url = None
            affected_orders += 1
            # 加一条 order_status_history 留痕
            self.db.add(OrderStatusHistory(
                order_id=order.id,
                from_status=order.status,
                to_status=order.status,
                source="system",
                note=f"user destroyed (user_id={user_id}) — PII scrubbed",
            ))

        # 3) 顶层 audit — 整个 user destroy 流程
        await record_audit(
            self.db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="cleanup.user_destroy.complete",
            target_type="user",
            target_id=user_id,
            payload={
                "deleted_materials": deleted_materials,
                "affected_orders": affected_orders,
                "freed_bytes": freed_bytes,
            },
        )

        # 4) 设 status=destroyed
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(status="destroyed", updated_at=_utcnow_naive())
        )

        await self.db.commit()
        duration_ms = int((time.monotonic() - start) * 1000)
        _log.info(
            "cleanup_user_data user_id={} deleted_materials={} affected_orders={} freed={}",
            user_id, deleted_materials, affected_orders, _human_bytes(freed_bytes),
        )
        return {
            "deleted_materials": deleted_materials,
            "affected_orders": affected_orders,
            "freed_bytes": freed_bytes,
            "duration_ms": duration_ms,
            "errors": errors,
        }

    # ====================================================================== #
    # 4) 跑 72h 注销扫描                                                       #
    # ====================================================================== #
    async def run_pending_destroy_users(
        self, *, actor_type: str = "system", actor_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """扫描 status=pending_destroy 且 updated_at > 72h 的用户,逐个 cleanup_user_data."""
        start = time.monotonic()
        cutoff = _utcnow_naive() - timedelta(hours=PENDING_DESTROY_MAX_AGE_HOURS)

        rows = (await self.db.execute(
            select(User).where(
                User.status == "pending_destroy",
                User.updated_at < cutoff,
            )
        )).scalars().all()

        affected_users: list[int] = []
        total_freed = 0
        total_materials = 0
        total_orders = 0
        errors: list[str] = []

        for user in rows:
            try:
                result = await self.cleanup_user_data(
                    user.id, actor_type=actor_type, actor_id=actor_id,
                )
                affected_users.append(user.id)
                total_freed += result["freed_bytes"]
                total_materials += result["deleted_materials"]
                total_orders += result["affected_orders"]
                errors.extend(result["errors"])
            except Exception as exc:
                _log.error("cleanup_user_data failed for user {}: {}", user.id, exc)
                errors.append(f"user[{user.id}]: {exc}")

        CleanupService._last_run_at = _utcnow_naive()
        duration_ms = int((time.monotonic() - start) * 1000)
        _log.info(
            "run_pending_destroy_users: processed={} freed={} duration={}ms",
            len(affected_users), _human_bytes(total_freed), duration_ms,
        )
        return {
            "deleted_count": len(affected_users),
            "freed_bytes": total_freed,
            "duration_ms": duration_ms,
            "affected_users": affected_users,
            "deleted_materials": total_materials,
            "affected_orders": total_orders,
            "errors": errors,
        }

    # ====================================================================== #
    # 5) 当前可清理量统计 (dashboard 展示)                                     #
    # ====================================================================== #
    async def get_stats(self) -> dict[str, Any]:
        """聚合查询:
          - temp_candidates : materials, created_at < 24h ago, storage_key 命中 tmp/temp
          - archive_candidates : materials, created_at < 180h ago, archived=true 或 storage_key 含 archive
          - pending_destroy_users : users, status=pending_destroy, updated_at < 72h ago
          - storage_bytes : 所有 alive materials 的 file_size 之和
        """
        temp_cutoff = _utcnow_naive() - timedelta(hours=TEMP_FILE_MAX_AGE_HOURS)
        archive_cutoff = _utcnow_naive() - timedelta(hours=ARCHIVE_FILE_MAX_AGE_HOURS)
        destroy_cutoff = _utcnow_naive() - timedelta(hours=PENDING_DESTROY_MAX_AGE_HOURS)

        # temp count
        q_temp = select(func.count()).select_from(Material).where(
            Material.deleted_at.is_(None),
            Material.created_at < temp_cutoff,
            (
                Material.storage_key.like("%/tmp/%")
                | Material.storage_key.like("%tmp_%")
                | Material.storage_key.like("%/temp/%")
                | Material.storage_key.like("%temp_%")
                | Material.storage_key.like("tmp/%")
                | Material.storage_key.like("temp/%")
            ),
        )
        temp_count = (await self.db.execute(q_temp)).scalar() or 0

        # archive count — Material.archived column + storage_key 关键词
        q_arch = select(Material).where(
            Material.deleted_at.is_(None),
            Material.created_at < archive_cutoff,
        )
        # 应用层二次过滤 (archived 或 storage_key 含 archive)
        arch_rows = (await self.db.execute(q_arch)).scalars().all()
        arch_count = sum(
            1 for r in arch_rows
            if getattr(r, "archived", False) or "archive" in (r.storage_key or "").lower()
        )

        # pending_destroy users
        q_pending = select(func.count()).select_from(User).where(
            User.status == "pending_destroy",
            User.updated_at < destroy_cutoff,
        )
        pending_count = (await self.db.execute(q_pending)).scalar() or 0

        # total storage bytes (alive)
        q_storage = select(func.coalesce(func.sum(Material.file_size), 0)).where(
            Material.deleted_at.is_(None),
        )
        storage_bytes = int((await self.db.execute(q_storage)).scalar() or 0)

        return {
            "temp_candidates": int(temp_count),
            "archive_candidates": int(arch_count),
            "pending_destroy_users": int(pending_count),
            "storage_bytes": int(storage_bytes),
            "last_run_at": CleanupService._last_run_at,
            "generated_at": _utcnow_naive(),
        }


# --------------------------------------------------------------------------- #
# 磁盘使用率辅助 (dashboard 显示)                                              #
# --------------------------------------------------------------------------- #
def get_disk_usage_percent(root: Optional[Path] = None) -> float:
    """返回 material_storage_root 的磁盘使用率 (0-100).

    shutil.disk_usage 在某些文件系统上可能失败 — 任何异常都返回 0.0 (不抛).
    """
    import shutil

    try:
        if root is None:
            root = storage.get_storage_root()
        usage = shutil.disk_usage(root)
        return round(usage.used / usage.total * 100, 2) if usage.total > 0 else 0.0
    except Exception:
        return 0.0


def get_db_size_bytes(db_url: Optional[str] = None) -> int:
    """SQLite DB 文件大小; Postgres 返回 0 (避免引入额外 SQL)."""
    from app.core.config import get_settings

    try:
        url = db_url or get_settings().database_url
        if "sqlite" not in url:
            return 0
        # sqlite:///abs/path or sqlite+aiosqlite:///abs/path
        path = url.split("///", 1)[-1]
        if not path:
            return 0
        p = Path(path)
        if p.exists():
            return int(p.stat().st_size)
        return 0
    except Exception:
        return 0