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
# GDPR retention (overridden by settings when available)
MATERIALS_RETENTION_DAYS = 90
APPLICANT_DATA_RETENTION_DAYS = 180

# Payment blob keys that may hold direct identifiers — strip on scrub.
_PAYMENT_PII_KEYS = frozenset(
    {
        "passport_no",
        "passport_number",
        "applicant_name",
        "full_name",
        "email",
        "phone",
        "id_number",
        "national_id",
    }
)


def _hash_email(email: str) -> str:
    import hashlib

    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:24]
    return f"deleted_{digest}@anon.invalid"


def _scrub_payment_blob(raw: Optional[str]) -> Optional[str]:
    """Keep payment status / amounts; drop direct identifiers from JSON blob."""
    if not raw:
        return raw
    import json

    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    for key in list(data.keys()):
        if key.lower() in _PAYMENT_PII_KEYS or "passport" in key.lower():
            data.pop(key, None)
    # Keep structural payment fields only
    keep = {
        k: v
        for k, v in data.items()
        if k
        in {
            "status",
            "channel",
            "trade_no",
            "amount_cents",
            "currency",
            "paid_at",
            "refunded_at",
            "refund_trade_no",
            "refund_amount_cents",
        }
    }
    return json.dumps(keep, ensure_ascii=False) if keep else None


def maybe_set_retention_anchor(order: Any, *, now: Optional[datetime] = None) -> None:
    """Stamp retention_anchor_at once when order hits a GDPR terminal state."""
    from app.models.order import TERMINAL_STATUSES

    # Also treat approved/rejected as retention anchors (plan wording).
    anchor_statuses = set(TERMINAL_STATUSES) | {"approved", "rejected"}
    status = getattr(order, "status", None)
    refund = getattr(order, "refund_status", None) or "none"
    should_anchor = status in anchor_statuses or refund == "completed"
    if not should_anchor:
        return
    if getattr(order, "retention_anchor_at", None) is not None:
        return
    order.retention_anchor_at = now or _utcnow_naive()


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
        """Hard-scrub PII for a destroyed account while keeping audit/payment shells.

        Steps:
          1. Physically delete materials + clear OCR JSON
          2. Scrub orders (applicant_data / extra / payment identifiers)
          3. Anonymize applicants
          4. Hash email, unlink OAuth, revoke sessions, mark destroyed
        """
        import json

        from app.models.applicant import Applicant
        from app.models.user_session import UserSession
        from app.core.security import invalidate_user_sessions

        start = time.monotonic()
        deleted_materials = 0
        freed_bytes = 0
        affected_orders = 0
        scrubbed_applicants = 0
        errors: list[str] = []

        # 1) Materials — all rows for user (including soft-deleted: wipe OCR)
        m_rows = (
            await self.db.execute(select(Material).where(Material.user_id == user_id))
        ).scalars().all()

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

            if row.deleted_at is None:
                try:
                    abs_path = storage.path_for(row.storage_key)
                    if abs_path.exists():
                        abs_path.unlink()
                        freed_bytes += int(row.file_size or 0)
                except Exception as exc:
                    _log.warning("physical delete failed for {}: {}", row.storage_key, exc)
                    errors.append(f"file[mat:{row.id}]: {exc}")
                row.deleted_at = _utcnow_naive()
                deleted_materials += 1

            row.ocr_result = None
            row.original_filename = "deleted"
            row.thumbnail_key = None

        # 2) Orders — scrub PII, keep order_no / status for finance
        o_rows = (
            await self.db.execute(select(Order).where(Order.user_id == user_id))
        ).scalars().all()
        for order in o_rows:
            order.applicant_data = None
            order.material_ids = None
            order.destination_url = None
            if hasattr(order, "ds160_code"):
                order.ds160_code = None
            if hasattr(order, "ds160_fingerprint"):
                order.ds160_fingerprint = None
            # Scrub payment / extra blobs
            if order.extra:
                try:
                    blob = json.loads(order.extra)
                    if isinstance(blob, dict):
                        payment = blob.get("payment")
                        if isinstance(payment, dict):
                            blob["payment"] = json.loads(
                                _scrub_payment_blob(json.dumps(payment)) or "{}"
                            )
                        for k in list(blob.keys()):
                            if k.lower() in _PAYMENT_PII_KEYS or "passport" in k.lower():
                                blob.pop(k, None)
                        order.extra = json.dumps(blob, ensure_ascii=False)
                    else:
                        order.extra = None
                except Exception:
                    order.extra = _scrub_payment_blob(order.extra)
            affected_orders += 1
            self.db.add(
                OrderStatusHistory(
                    order_id=order.id,
                    from_status=order.status,
                    to_status=order.status,
                    source="system",
                    note=f"user destroyed (user_id={user_id}) — PII scrubbed",
                )
            )

        # 3) Applicants — anonymize (keep row count for integrity, wipe PII)
        a_rows = (
            await self.db.execute(select(Applicant).where(Applicant.user_id == user_id))
        ).scalars().all()
        for app in a_rows:
            app.surname = "DELETED"
            app.given_name = "USER"
            app.passport_no = f"X{user_id:08d}{app.id:04d}"[:32]
            app.is_minor = False
            app.guardian_relationship = None
            scrubbed_applicants += 1

        # 4) User identity scrub + session revoke
        user = await self.db.get(User, user_id)
        if user is not None:
            if user.email and not user.email.startswith("deleted_"):
                user.email = _hash_email(user.email)
            user.google_sub = None
            user.wechat_openid = None
            user.nickname = None
            user.avatar_url = None
            user.email_pending = None
            user.mfa_secret = None
            user.mfa_enabled = False
            user.password_hash = None
            user.status = "destroyed"
            user.updated_at = _utcnow_naive()

        try:
            await invalidate_user_sessions(self.db, user_id)
        except Exception:
            now = _utcnow_naive()
            await self.db.execute(
                update(UserSession)
                .where(
                    UserSession.user_id == user_id,
                    UserSession.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )

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
                "scrubbed_applicants": scrubbed_applicants,
                "freed_bytes": freed_bytes,
            },
        )

        await self.db.commit()
        duration_ms = int((time.monotonic() - start) * 1000)
        _log.info(
            "cleanup_user_data user_id={} deleted_materials={} affected_orders={} "
            "applicants={} freed={}",
            user_id,
            deleted_materials,
            affected_orders,
            scrubbed_applicants,
            _human_bytes(freed_bytes),
        )
        return {
            "deleted_materials": deleted_materials,
            "affected_orders": affected_orders,
            "scrubbed_applicants": scrubbed_applicants,
            "freed_bytes": freed_bytes,
            "duration_ms": duration_ms,
            "errors": errors,
        }

    # ====================================================================== #
    # 3b) Retention purge — materials 90d / applicant_data 180d               #
    # ====================================================================== #
    async def run_retention_purge(
        self, *, actor_type: str = "system", actor_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Purge materials and applicant_data after configured retention windows."""
        from app.core.config import get_settings

        settings = get_settings()
        mat_days = int(getattr(settings, "retention_materials_days", MATERIALS_RETENTION_DAYS))
        app_days = int(
            getattr(settings, "retention_applicant_data_days", APPLICANT_DATA_RETENTION_DAYS)
        )

        start = time.monotonic()
        now = _utcnow_naive()
        mat_cutoff = now - timedelta(days=mat_days)
        app_cutoff = now - timedelta(days=app_days)

        deleted_materials = 0
        freed_bytes = 0
        scrubbed_orders = 0
        errors: list[str] = []

        # Materials linked to orders past material retention
        order_ids_mat = (
            await self.db.execute(
                select(Order.id).where(
                    Order.retention_anchor_at.is_not(None),
                    Order.retention_anchor_at < mat_cutoff,
                )
            )
        ).scalars().all()

        if order_ids_mat:
            m_rows = (
                await self.db.execute(
                    select(Material).where(
                        Material.deleted_at.is_(None),
                        Material.order_id.in_(list(order_ids_mat)),
                    )
                )
            ).scalars().all()
            # Also purge orphan materials whose order is in the set via material_ids —
            # primary path is order_id FK above. User-owned materials without order_id
            # are kept until account destroy.
            for row in m_rows:
                try:
                    await record_audit(
                        self.db,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        action="cleanup.retention.material",
                        target_type="material",
                        target_id=row.id,
                        payload={"storage_key": row.storage_key, "reason": f">{mat_days}d"},
                    )
                except Exception as exc:
                    errors.append(f"audit[mat:{row.id}]: {exc}")
                try:
                    abs_path = storage.path_for(row.storage_key)
                    if abs_path.exists():
                        abs_path.unlink()
                        freed_bytes += int(row.file_size or 0)
                except Exception as exc:
                    errors.append(f"file[mat:{row.id}]: {exc}")
                row.deleted_at = now
                row.ocr_result = None
                deleted_materials += 1

        # Applicant structured data past 180d
        o_rows = (
            await self.db.execute(
                select(Order).where(
                    Order.retention_anchor_at.is_not(None),
                    Order.retention_anchor_at < app_cutoff,
                    Order.applicant_data.is_not(None),
                )
            )
        ).scalars().all()
        for order in o_rows:
            order.applicant_data = None
            if order.extra:
                order.extra = _scrub_payment_blob(order.extra) or order.extra
            scrubbed_orders += 1
            self.db.add(
                OrderStatusHistory(
                    order_id=order.id,
                    from_status=order.status,
                    to_status=order.status,
                    source="system",
                    note=f"retention purge applicant_data after {app_days}d",
                )
            )

        await self.db.commit()
        CleanupService._last_run_at = now
        duration_ms = int((time.monotonic() - start) * 1000)
        _log.info(
            "run_retention_purge: materials={} orders={} freed={} duration={}ms",
            deleted_materials,
            scrubbed_orders,
            _human_bytes(freed_bytes),
            duration_ms,
        )
        return {
            "deleted_materials": deleted_materials,
            "scrubbed_orders": scrubbed_orders,
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