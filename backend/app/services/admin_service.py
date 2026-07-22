"""AdminService — all admin-panel business logic.

Independent from C-user service layer. Handles:
  - Admin login (password verified against ADMIN_PASSWORD env var)
  - User management (list/detail/soft-delete)
  - Order management (list/detail/update-status)
  - Country config CRUD
  - Validation rules CRUD
  - RPA config read/update
  - RPA realtime stats (today visits / queue size / 24h failure rate)
  - Audit log pagination
"""
import json
import math
import secrets
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.product_scope import (
    PRODUCT_DESTINATION_CODES,
    normalize_destination_code,
)
from app.core.security import bump_password_changed_at, invalidate_user_sessions
from app.middleware.admin_auth import create_admin_token
from app.models.audit_log import AuditLog
from app.models.material import Material
from app.models.order import (
    Order,
    OrderStatusHistory,
    ORDER_STATUSES,
    is_valid_transition,
    next_statuses,
)
from app.models.destination import VisaDestination
from app.models.user import User
from app.models.visa_countries import VisaCountry
from app.models.validation_rules import ValidationRule
from app.models.admin_role import AdminRole
from app.models.admin_user import AdminUser
from app.models.i18n_override import I18nOverride
from app.services.audit import record_audit


def _get_rpa_scheduler_singleton():
    """Late import to avoid circular deps at module load."""
    from app.services.rpa.rpa_scheduler import RPAScheduler, TaskStatus

    # The rpa router module owns the singleton; reuse it when available.
    try:
        from app.api.v2 import rpa as rpa_api

        return rpa_api.get_scheduler(), TaskStatus
    except Exception:  # pragma: no cover — defensive
        return RPAScheduler(), TaskStatus


_log = get_logger()


def _parse_iso(val):
    """解析 ISO 格式时间字符串为 datetime（naive UTC），失败返回 None。"""
    if not val:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(val)).replace(tzinfo=None)
    except Exception:
        return None


class AdminService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    # ------------------------------------------------------------------ #
    # Auth                                                                  #
    # ------------------------------------------------------------------ #
    async def login(self, username: str, password: str) -> dict[str, Any]:
        """Verify admin credentials and return a JWT token pair.

        认证顺序（W34）：
          1. 先查 admin_users 表（DB 中的账号）
          2. 回退到 ADMIN_PASSWORD_SECRET / ADMIN_PASSWORD（兼容旧 env 方式，username 必须是 admin）
        """
        import bcrypt
        from datetime import datetime, timezone

        # 1) 尝试 DB 账号
        user = (
            await self.db.execute(
                select(AdminUser).where(
                    AdminUser.username == username,
                    AdminUser.is_active == True  # noqa: E712
                )
            )
        ).scalar_one_or_none()

        if user:
            if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
                raise BizException(
                    ErrorCode.AUTH_INVALID_CREDENTIALS, message="Invalid admin credentials"
                )
            admin_id = user.id
            role = (await self.db.execute(select(AdminRole).where(AdminRole.id == user.role_id))).scalar_one_or_none()
            permissions = role.permissions if role else []
            role_name = role.name if role else ""
            role_code = role.code if role else ""

            # 更新最后登录时间
            user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            # 2) 回退到 env 密码（仅 username=admin 且 DB 中无该账号时）
            if username != "admin":
                raise BizException(
                    ErrorCode.AUTH_INVALID_CREDENTIALS, message="Invalid admin credentials"
                )
            admin_password = (
                self.settings.admin_password_secret
                or self.settings.admin_password
                or "CHANGE_ME_IN_PROD"
            )
            if password != admin_password:
                raise BizException(
                    ErrorCode.AUTH_INVALID_CREDENTIALS, message="Invalid admin credentials"
                )
            admin_id = 0
            # W63: env fallback 用全 perm code (跟 super_admin role 一致),
            # 之前用简写 ["dashboard","orders",...] 导致前端 hasPermission 把细粒度 perm
            # (dashboard.view / order.view / ...) 都判 false,管理后台侧栏菜单残缺。
            from app.core.permissions import all_perm_codes
            permissions = all_perm_codes()
            role_name = "超级管理员（env）"
            role_code = "super_admin"

        token, exp = create_admin_token(
            admin_id=admin_id, username=username, permissions=permissions
        )
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=admin_id,
            action="admin.login",
            payload={"username": username, "source": "db" if user else "env"},
        )
        await self.db.commit()
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self.settings.access_token_ttl_minutes * 60,
            "username": username,
            "role_name": role_name,
            "permissions": permissions,
        }

    # ------------------------------------------------------------------ #
    # User management                                                      #
    # ------------------------------------------------------------------ #

    # 通用：序列化用户为脱敏前的原始 dict（service 层出入口）
    def _serialize_user(self, u: User) -> dict[str, Any]:
        return {
            "id": u.id,
            "uuid": u.uuid,
            "email": u.email,
            "username": u.username,
            "nickname": u.nickname,
            "avatar_url": u.avatar_url,
            "language_pref": u.language_pref or "zh-CN",
            "status": u.status,
            "mfa_enabled": bool(u.mfa_enabled),
            "last_login_at": u.last_login_at,
            "last_login_ip": u.last_login_ip,
            "created_at": u.created_at,
            "updated_at": u.updated_at,
        }

    async def _user_counts(self, user_id: int) -> tuple[int, int]:
        """返回 (order_count, material_count) — 两个独立 COUNT 查询并行执行。"""
        order_count = (
            await self.db.execute(
                select(func.count()).select_from(Order).where(Order.user_id == user_id)
            )
        ).scalar() or 0
        material_count = (
            await self.db.execute(
                select(func.count()).select_from(Material).where(Material.user_id == user_id)
            )
        ).scalar() or 0
        return int(order_count), int(material_count)

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        q: Optional[str] = None,
    ) -> dict[str, Any]:
        """Paginated user list, optionally filtered by status.

        W63: 列表里直接给 order_count / material_count,免得前端详情抽屉没数。
        一次 group-by 查询把当前页所有用户的两个 count 拉出来,避免 N+1。
        """
        query = select(User).order_by(User.created_at.desc())
        if status:
            query = query.where(User.status == status)
        if q and q.strip():
            term = f"%{q.strip()}%"
            query = query.where(
                or_(
                    User.email.ilike(term),
                    User.username.ilike(term),
                    User.nickname.ilike(term),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        items = [self._serialize_user(r) for r in rows]

        # W63: batch 算 order_count / material_count (group by user_id 一次拉)
        if items:
            user_ids = [u["id"] for u in items]
            order_rows = (
                await self.db.execute(
                    select(Order.user_id, func.count())
                    .where(Order.user_id.in_(user_ids))
                    .group_by(Order.user_id)
                )
            ).all()
            mat_rows = (
                await self.db.execute(
                    select(Material.user_id, func.count())
                    .where(Material.user_id.in_(user_ids))
                    .group_by(Material.user_id)
                )
            ).all()
            order_map = {uid: cnt for uid, cnt in order_rows}
            mat_map = {uid: cnt for uid, cnt in mat_rows}
            for u in items:
                u["order_count"] = int(order_map.get(u["id"], 0))
                u["material_count"] = int(mat_map.get(u["id"], 0))

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        }

    async def get_user(self, user_id: int) -> dict[str, Any]:
        """User detail (raw — service-level dict, schema layer masks email/phone)."""
        user = await self.db.get(User, user_id)
        if user is None:
            raise BizException(ErrorCode.USER_NOT_FOUND, message="User not found")
        return self._serialize_user(user)

    async def get_user_detail(self, user_id: int) -> dict[str, Any]:
        """用户详情（含 order_count / material_count）。"""
        raw = await self.get_user(user_id)
        order_count, material_count = await self._user_counts(user_id)
        raw["order_count"] = order_count
        raw["material_count"] = material_count
        return raw

    async def update_user(
        self, user_id: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        """修改 C-端用户基本信息（仅允许 nickname / language_pref / avatar_url）。
        email / username / password 不在此接口暴露（走专门接口）。
        """
        user = await self.db.get(User, user_id)
        if user is None:
            raise BizException(ErrorCode.USER_NOT_FOUND, message="User not found")

        # 字段级白名单：哪怕有遗漏字段注入也不会落库
        allowed = {"nickname", "language_pref", "avatar_url"}
        updates = {k: v for k, v in data.items() if k in allowed and v is not None}
        if not updates:
            raise BizException(
                ErrorCode.INVALID_PARAMS,
                message="没有可更新的字段（仅 nickname / language_pref / avatar_url）",
            )

        # 简单校验（与 Pydantic 字段一致的双重校验）
        if "language_pref" in updates:
            lp = updates["language_pref"]
            if lp not in ("zh-CN", "en", "id-ID", "vi-VN"):
                raise BizException(
                    ErrorCode.INVALID_PARAMS,
                    message=f"不支持的语言: {lp}",
                )

        for k, v in updates.items():
            setattr(user, k, v)

        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.user.update",
            target_type="user",
            target_id=user_id,
            payload={"updated_fields": list(updates.keys())},
        )
        await self.db.commit()
        await self.db.refresh(user)
        return self._serialize_user(user)

    async def disable_user(self, user_id: int) -> dict[str, Any]:
        """禁用账号 (status='disabled'). 任意非 destroyed 状态都可禁用。"""
        user = await self.db.get(User, user_id)
        if user is None:
            raise BizException(ErrorCode.USER_NOT_FOUND, message="User not found")
        if user.status == "destroyed":
            raise BizException(
                ErrorCode.CONFLICT, message="已销毁的账号不可禁用"
            )
        if user.status == "disabled":
            # idempotent: 已经是 disabled 直接返回
            return self._serialize_user(user)

        old_status = user.status
        user.status = "disabled"
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.user.disable",
            target_type="user",
            target_id=user_id,
            payload={"from": old_status, "to": "disabled"},
        )
        await self.db.commit()
        await self.db.refresh(user)
        return self._serialize_user(user)

    async def restore_user(self, user_id: int) -> dict[str, Any]:
        """恢复账号 (status='active'). 仅当 status='disabled' 时可用。"""
        user = await self.db.get(User, user_id)
        if user is None:
            raise BizException(ErrorCode.USER_NOT_FOUND, message="User not found")
        if user.status != "disabled":
            raise BizException(
                ErrorCode.CONFLICT,
                message=f"仅可恢复 disabled 账号，当前 status={user.status}",
                data={"current_status": user.status},
            )

        user.status = "active"
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.user.restore",
            target_type="user",
            target_id=user_id,
            payload={"from": "disabled", "to": "active"},
        )
        await self.db.commit()
        await self.db.refresh(user)
        return self._serialize_user(user)

    async def reset_user_password(self, user_id: int) -> dict[str, Any]:
        """重置 C-端用户密码：生成 12 位随机密码（大小写 + 数字 + 符号），返回一次明文。"""
        import bcrypt

        user = await self.db.get(User, user_id)
        if user is None:
            raise BizException(ErrorCode.USER_NOT_FOUND, message="User not found")
        if not user.email and not user.username:
            raise BizException(
                ErrorCode.CONFLICT,
                message="用户无任何登录标识（无 email/username）",
            )

        # 12 位随机密码，含大小写 + 数字 + 符号（至少各 1）
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        while True:
            new_pwd = "".join(secrets.choice(alphabet) for _ in range(12))
            # 保证至少 1 个数字 + 1 个字母
            if (
                any(c.isdigit() for c in new_pwd)
                and any(c.isalpha() for c in new_pwd)
            ):
                break

        user.password_hash = bcrypt.hashpw(
            new_pwd.encode(), bcrypt.gensalt()
        ).decode()
        bump_password_changed_at(user)
        await invalidate_user_sessions(self.db, user.id)

        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.user.reset_password",
            target_type="user",
            target_id=user_id,
            payload={"username": user.username, "email": user.email},
        )
        await self.db.commit()

        return {
            "user_id": user_id,
            "username": user.username,
            "new_password": new_pwd,
            "reset_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }

    async def list_user_orders(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """某 C-端用户关联的订单列表（分页）。"""
        # 先确认 user 存在（避免 user_id 拼错时返回空）
        user = await self.db.get(User, user_id)
        if user is None:
            raise BizException(ErrorCode.USER_NOT_FOUND, message="User not found")

        query = (
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
        )
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        rows = (
            await self.db.execute(query.offset(offset).limit(page_size))
        ).scalars().all()

        items = [
            {
                "id": r.id,
                "order_no": r.order_no,
                "visa_type": r.visa_type,
                "status": r.status,
                "total_amount": float(r.total_amount),
                "currency": r.currency,
                "destination_id": r.destination_id,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        }

    async def delete_user(self, user_id: int) -> None:
        """Soft-delete: set status = 'pending_destroy'."""
        user = await self.db.get(User, user_id)
        if user is None:
            raise BizException(ErrorCode.USER_NOT_FOUND, message="User not found")
        user.status = "pending_destroy"
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.user.delete",
            target_type="user",
            target_id=user_id,
        )
        await self.db.commit()

    # ------------------------------------------------------------------ #
    # Order management                                                      #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _order_attention_hint(order: Order) -> Optional[str]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if order.status == "created" and order.locked_until and order.locked_until <= now + timedelta(minutes=15):
            return "payment_expiring_soon"
        if order.status == "paid" and not order.diagnosis_completed_at:
            return "paid_awaiting_diagnosis"
        if order.status == "completed" and not order.portal_submitted_at:
            return "completed_awaiting_portal"
        if (order.refund_status or "none") == "pending":
            return "refund_pending"
        if order.refund_status == "failed":
            return "refund_failed"
        return None

    async def list_orders(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Paginated order list, optionally filtered."""
        query = select(Order).order_by(Order.created_at.desc())
        if status:
            query = query.where(Order.status == status)
        if user_id:
            query = query.where(Order.user_id == user_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        # Add display metadata without changing any existing response fields or
        # persistence. Older clients can keep consuming ids; the admin UI can
        # present names instead of leaking database identifiers.
        user_ids = {r.user_id for r in rows}
        destination_ids = {r.destination_id for r in rows}
        users = {}
        destinations = {}
        if user_ids:
            user_rows = (
                await self.db.execute(select(User).where(User.id.in_(user_ids)))
            ).scalars().all()
            users = {u.id: u for u in user_rows}
        if destination_ids:
            destination_rows = (
                await self.db.execute(
                    select(VisaDestination).where(VisaDestination.id.in_(destination_ids))
                )
            ).scalars().all()
            destinations = {d.id: d for d in destination_rows}

        return {
            "items": [
                {
                    "id": r.id,
                    "uuid": r.uuid,
                    "order_no": r.order_no,
                    "user_id": r.user_id,
                    "user_name": (
                        users[r.user_id].nickname
                        or users[r.user_id].username
                        or users[r.user_id].email
                    ) if r.user_id in users else None,
                    "user_email": users[r.user_id].email if r.user_id in users else None,
                    "destination_id": r.destination_id,
                    "country_code": destinations[r.destination_id].country_code
                    if r.destination_id in destinations else None,
                    "country_name": self._destination_display_name(destinations[r.destination_id])
                    if r.destination_id in destinations else None,
                    "visa_type": r.visa_type,
                    "status": r.status,
                    "total_amount": float(r.total_amount),
                    "currency": r.currency,
                    "rpa_task_id": r.rpa_task_id,
                    "aff_code": r.aff_code,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        }

    async def get_order(self, order_id: int) -> dict[str, Any]:
        """Order detail (admin view) with status history + audit logs + allowed transitions.

        W34: also returns `allowed_next_statuses` so the admin UI can render
        only the action buttons that the server would accept. This avoids
        the user clicking "approve" on a `closed` order and getting a
        confusing 4012.
        """

        # Eager-load status_history (audit timeline shown in the detail page)
        stmt = (
            select(Order)
            .options(selectinload(Order.status_history))
            .where(Order.id == order_id)
        )
        order = (await self.db.execute(stmt)).scalar_one_or_none()
        if order is None:
            raise BizException(ErrorCode.ORDER_NOT_FOUND, message="Order not found")

        user = await self.db.get(User, order.user_id)
        destination = await self.db.get(VisaDestination, order.destination_id)

        # 从 order.extra JSON 解析支付信息（W34: 订单与资金流分开）
        payment_info = None
        if order.extra:
            try:
                extra = json.loads(order.extra) if isinstance(order.extra, str) else order.extra
                if "payment" in extra:
                    p = extra["payment"]
                    payment_info = {
                        "trade_no": p.get("trade_no"),
                        "status": p.get("status", "none"),
                        "paid_at": p.get("paid_at"),
                        "amount_cents": p.get("amount_cents", 0),
                        "currency": p.get("currency", "USD"),
                        "code_url": p.get("code_url"),
                        "expired_at": p.get("expired_at"),
                    }
            except Exception:
                pass

        # 查询 audit_log 表中所有与该订单相关的日志（W34: 完整日志区块）
        audit_rows = (
            await self.db.execute(
                select(AuditLog)
                .where(
                    (AuditLog.target_type == "order") & (AuditLog.target_id == order_id)
                )
                .order_by(AuditLog.created_at.desc())
                .limit(50)
            )
        ).scalars().all()

        audit_logs = [
            {
                "id": r.id,
                "actor_type": r.actor_type,
                "actor_id": r.actor_id,
                "action": r.action,
                "payload": r.payload,
                "created_at": r.created_at,
            }
            for r in audit_rows
        ]

        return {
            "id": order.id,
            "uuid": order.uuid,
            "order_no": order.order_no,
            "user_id": order.user_id,
            "user_name": (user.nickname or user.username or user.email) if user else None,
            "user_email": user.email if user else None,
            "destination_id": order.destination_id,
            "country_code": destination.country_code if destination else None,
            "country_name": self._destination_display_name(destination) if destination else None,
            "visa_type": order.visa_type,
            "status": order.status,
            "total_amount": float(order.total_amount),
            "currency": order.currency,
            "rpa_task_id": order.rpa_task_id,
            "aff_code": order.aff_code,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "submitted_at": order.submitted_at,
            "reviewed_at": order.reviewed_at,
            "closed_at": order.closed_at,
            "locked_until": order.locked_until,
            "paid_at": order.paid_at,
            "diagnosis_completed_at": order.diagnosis_completed_at,
            "completed_at": order.completed_at,
            "portal_submitted_at": order.portal_submitted_at,
            "portal_submitted_source": order.portal_submitted_source,
            "refund_status": order.refund_status or "none",
            "refund_reason": order.refund_reason,
            "refund_amount": float(order.refund_amount) if order.refund_amount is not None else None,
            "refund_requested_at": order.refund_requested_at,
            "refund_approved_at": order.refund_approved_at,
            "refunded_at": order.refunded_at,
            "attention_hint": self._order_attention_hint(order),
            "applicant_data": order.applicant_data,
            "material_ids": order.material_ids,
            "destination_url": order.destination_url,
            "status_history": [
                {
                    "from_status": h.from_status,
                    "to_status": h.to_status,
                    "source": h.source,
                    "note": h.note,
                    "created_at": h.created_at,
                }
                for h in sorted(order.status_history, key=lambda x: x.created_at)
            ],
            "allowed_next_statuses": sorted(next_statuses(order.status)),
            "payment": payment_info,
            "audit_logs": audit_logs,
        }

    async def update_order_status(
        self, order_id: int, new_status: str, note: Optional[str] = None,
        admin: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Update order status (admin override).

        W34: validate the transition through `is_valid_transition` so admins
        can't move an order from `closed` back to `created`, etc. Append
        a corresponding `OrderStatusHistory` row (was missing before — the
        user-side paths write history, but admin overrides silently
        flipped the status without leaving a trail).

        W47: 二次 perm 校验 — 根据目标 status 决定额外需要的 perm:
          - close / abnormal / failed → 需要 order.close
          - 其它编辑 (approved / rejected / submitted / processing …) → 已有 order.edit_status
          - rpa 重派 / 重置 在专门的接口上,不在此函数校验
        """
        order = await self.db.get(Order, order_id)
        if order is None:
            raise BizException(ErrorCode.ORDER_NOT_FOUND, message="Order not found")
        if new_status not in ORDER_STATUSES:
            raise BizException(
                ErrorCode.ORDER_INVALID_STATE, message=f"Invalid status: {new_status}"
            )

        # W47: perm 二次校验 — close 类动作额外要 order.close
        if new_status in ("closed", "abnormal", "failed"):
            if admin is not None and admin.role_code != "super_admin":
                if "order.close" not in (admin.permissions or []):
                    raise BizException(
                        ErrorCode.FORBIDDEN,
                        message="关闭订单需要 order.close 权限",
                        data={"required_perm": "order.close"},
                    )

        old_status = order.status
        if not is_valid_transition(old_status, new_status):
            raise BizException(
                ErrorCode.ORDER_INVALID_STATE,
                message=(
                    f"Illegal status transition: {old_status} → {new_status}. "
                    f"Allowed next states from '{old_status}': "
                    f"{sorted(next_statuses(old_status)) or 'none (terminal)'}."
                ),
                data={
                    "from_status": old_status,
                    "to_status": new_status,
                    "allowed": sorted(next_statuses(old_status)),
                },
            )
        order.status = new_status
        # W34: also stamp terminal-relevant timestamps so downstream
        # consumers can sort without joining status_history. Abnormal and
        # failed are also terminal states (per is_valid_transition +
        # TERMINAL_STATUSES in app/models/order.py) — they share the
        # closed_at column with `closed` so dashboard / audit queries can
        # group them as "ended" uniformly. Sync with PollService.record_change
        # which uses the same convention.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if new_status in ("closed", "abnormal", "failed"):
            order.closed_at = now
        elif new_status in ("approved", "rejected"):
            order.reviewed_at = now
        elif new_status == "paid":
            order.paid_at = order.paid_at or now
        elif new_status == "completed":
            order.completed_at = order.completed_at or now
            order.diagnosis_completed_at = order.diagnosis_completed_at or now
        elif new_status == "cancelled":
            order.closed_at = order.closed_at or now
        from app.services.cleanup_service import maybe_set_retention_anchor
        maybe_set_retention_anchor(order, now=now)
        # Status history (was missing for admin overrides — audit 5.0
        # would have caught this in retrospect).
        self.db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=old_status,
                to_status=new_status,
                source="admin",
                note=note or f"admin override: {old_status} → {new_status}",
            )
        )
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.order.update_status",
            target_type="order",
            target_id=order_id,
            payload={
                "order_no": order.order_no,
                "from_status": old_status,
                "to_status": new_status,
                "note": note,
            },
        )
        await self.db.commit()
        # Reload attributes that may have been expired by the commit (SQLAlchemy
        # async session needs refresh, otherwise accessing updated_at raises
        # MissingGreenlet on lazy-load)
        await self.db.refresh(order)
        return {
            "id": order.id,
            "order_no": order.order_no,
            "status": order.status,
            "updated_at": order.updated_at,
        }

    async def update_order_refund(
        self,
        order_id: int,
        action: str,
        *,
        admin_id: int = 0,
        note: Optional[str] = None,
    ) -> dict[str, Any]:
        """Admin refund sub-track: approve | reject | complete | fail."""
        from app.models.order import REFUND_STATUSES

        order = await self.db.get(Order, order_id)
        if order is None:
            raise BizException(ErrorCode.ORDER_NOT_FOUND, message="Order not found")

        valid_actions = {
            "approve": ("pending", "approved"),
            "reject": ("pending", "rejected"),
            "complete": ("approved", "completed"),
            "fail": ("approved", "failed"),
        }
        if action not in valid_actions:
            raise BizException(ErrorCode.INVALID_PARAMS, message=f"action must be one of {list(valid_actions)}")

        expected_from, new_status = valid_actions[action]
        current = order.refund_status or "none"
        if current != expected_from:
            raise BizException(
                ErrorCode.ORDER_INVALID_STATE,
                message=f"Refund status must be '{expected_from}', got '{current}'",
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if action == "complete":
            from app.services.payment_provider import get_payment_provider

            amount_cents = None
            if order.refund_amount is not None:
                amount_cents = int(float(order.refund_amount) * 100)
            try:
                await get_payment_provider().refund_order(
                    self.db,
                    order_no=order.order_no,
                    amount_cents=amount_cents,
                    reason=order.refund_reason,
                )
            except LookupError as exc:
                raise BizException(
                    ErrorCode.PAYMENT_NOT_FOUND,
                    message=str(exc),
                ) from exc
            except ValueError as exc:
                raise BizException(
                    ErrorCode.PAYMENT_AMOUNT_INVALID,
                    message=str(exc),
                ) from exc
            order.refunded_at = now

        order.refund_status = new_status
        if action == "approve":
            order.refund_approved_at = now
            order.refund_reviewed_by = admin_id or None
        if new_status == "completed":
            from app.services.cleanup_service import maybe_set_retention_anchor
            maybe_set_retention_anchor(order, now=now)
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=admin_id,
            action=f"admin.order.refund.{action}",
            target_type="order",
            target_id=order_id,
            payload={"order_no": order.order_no, "note": note, "refund_status": new_status},
        )
        await self.db.commit()
        await self.db.refresh(order)
        return {
            "id": order.id,
            "order_no": order.order_no,
            "refund_status": order.refund_status,
            "refunded_at": order.refunded_at,
        }

    async def mark_order_portal_submitted(
        self, order_id: int, *, admin_id: int = 0,
    ) -> dict[str, Any]:
        order = await self.db.get(Order, order_id)
        if order is None:
            raise BizException(ErrorCode.ORDER_NOT_FOUND, message="Order not found")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if order.portal_submitted_at is None:
            order.portal_submitted_at = now
            order.portal_submitted_source = "admin"
            order.ds160_portal_submitted_at = order.ds160_portal_submitted_at or now
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=admin_id,
            action="admin.order.portal.submitted",
            target_type="order",
            target_id=order_id,
            payload={"order_no": order.order_no},
        )
        await self.db.commit()
        await self.db.refresh(order)
        return {
            "id": order.id,
            "order_no": order.order_no,
            "portal_submitted_at": order.portal_submitted_at,
        }

    # ------------------------------------------------------------------ #
    # Country config                                                        #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _serialize_country(r: VisaCountry) -> dict[str, Any]:
        """Map a VisaCountry ORM row to its API dict — single source of truth.

        Centralised so list / create / update / toggle / reorder all return
        the same shape (V2 frontend schema: includes visa_types as list,
        display_order, form_template_url, description, flag_emoji, capital_city).
        """
        visa_types_value: Any = None
        if r.visa_types:
            try:
                visa_types_value = json.loads(r.visa_types)
            except Exception:
                visa_types_value = None

        return {
            "id": r.id,
            "country_code": r.country_code,
            "country_name_zh": r.country_name_zh,
            "country_name_en": r.country_name_en,
            "enabled": r.enabled,
            "display_order": r.display_order,
            "base_url": r.base_url,
            "form_path": r.form_path,
            "form_template_url": r.form_template_url,
            "rpa_config": r.rpa_config,
            "visa_types": visa_types_value,
            "fee_usd": r.fee_usd,
            "processing_days": r.processing_days,
            "description": r.description,
            "flag_emoji": r.flag_emoji,
            "capital_city": r.capital_city,
            "extra": r.extra,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }

    async def _sync_destination_enabled(self, country_code: str, enabled: bool) -> None:
        """Mirror admin country toggle onto visa_destinations (public picker + order guard).

        Matches UK↔GB. No-op when no destination row exists yet (admin-only config).
        """
        norm = normalize_destination_code(country_code)
        codes = {norm}
        if norm == "GB":
            codes.add("UK")
        elif norm == "UK":
            codes.add("GB")
        rows = (
            await self.db.execute(
                select(VisaDestination).where(VisaDestination.country_code.in_(codes))
            )
        ).scalars().all()
        for dest in rows:
            dest.enabled = enabled

    # Product destination cards shown on homepage / apply (US·AU·GB + Schengen DE/FR)
    _PRODUCT_COUNTRY_SEED: list[dict[str, Any]] = [
        {
            "country_code": "US",
            "country_name_zh": "美国",
            "country_name_en": "United States",
            "flag_emoji": "🇺🇸",
            "display_order": 1,
            "visa_types": ["tourism", "student"],
        },
        {
            "country_code": "AU",
            "country_name_zh": "澳大利亚",
            "country_name_en": "Australia",
            "flag_emoji": "🇦🇺",
            "display_order": 2,
            "visa_types": ["tourism"],
        },
        {
            "country_code": "GB",
            "country_name_zh": "英国",
            "country_name_en": "United Kingdom",
            "flag_emoji": "🇬🇧",
            "display_order": 3,
            "visa_types": ["tourism"],
        },
        {
            "country_code": "DE",
            "country_name_zh": "德国(申根)",
            "country_name_en": "Germany (Schengen)",
            "flag_emoji": "🇩🇪",
            "display_order": 4,
            "visa_types": ["tourism"],
        },
        {
            "country_code": "FR",
            "country_name_zh": "法国(申根)",
            "country_name_en": "France (Schengen)",
            "flag_emoji": "🇫🇷",
            "display_order": 5,
            "visa_types": ["tourism"],
        },
    ]

    async def ensure_product_countries(self) -> int:
        """Insert missing product destination rows; purge non-product legacy rows.

        Idempotent. Does not overwrite an existing product row's ``enabled`` flag.
        Deletes ID/VN/PH/… from ``visa_countries`` — we do not file those visas.
        Returns the number of product rows inserted.
        """
        from app.core.product_scope import NON_PRODUCT_DESTINATION_CODES

        # Drop legacy "file these visas" rows (ID/VN/PH etc.) from admin config
        purged = (
            await self.db.execute(
                select(VisaCountry).where(
                    VisaCountry.country_code.in_(
                        sorted(NON_PRODUCT_DESTINATION_CODES)
                    )
                )
            )
        ).scalars().all()
        for row in purged:
            await self.db.delete(row)

        inserted = 0
        touched = bool(purged)
        product_norm = {
            normalize_destination_code(c) for c in PRODUCT_DESTINATION_CODES
        }
        for spec in self._PRODUCT_COUNTRY_SEED:
            code = spec["country_code"]
            if normalize_destination_code(code) not in product_norm:
                continue
            existing = await self.db.scalar(
                select(VisaCountry).where(VisaCountry.country_code == code)
            )
            if existing is not None:
                # Backfill blank display fields only
                if not existing.country_name_zh:
                    existing.country_name_zh = spec["country_name_zh"]
                    touched = True
                if not existing.country_name_en:
                    existing.country_name_en = spec["country_name_en"]
                    touched = True
                if not existing.flag_emoji:
                    existing.flag_emoji = spec["flag_emoji"]
                    touched = True
                if not existing.visa_types:
                    existing.visa_types = json.dumps(spec["visa_types"], ensure_ascii=False)
                    touched = True
                continue

            # Default enabled from matching destination row when present
            dest = await self.db.scalar(
                select(VisaDestination).where(
                    VisaDestination.country_code.in_(
                        {code, "UK"} if code == "GB" else {code}
                    )
                )
            )
            enabled = bool(dest.enabled) if dest is not None else True
            self.db.add(
                VisaCountry(
                    country_code=code,
                    country_name_zh=spec["country_name_zh"],
                    country_name_en=spec["country_name_en"],
                    flag_emoji=spec["flag_emoji"],
                    display_order=spec["display_order"],
                    visa_types=json.dumps(spec["visa_types"], ensure_ascii=False),
                    enabled=enabled,
                )
            )
            inserted += 1
            touched = True
        if touched:
            await self.db.commit()
        return inserted

    async def list_countries(
        self,
        page: int = 1,
        page_size: int = 50,
        enabled: Optional[bool] = None,
        product_only: bool = True,
    ) -> dict[str, Any]:
        """Paginated country list.

        Sorted by ``display_order`` ascending (then country_code as a stable
        tie-breaker) so the admin table mirrors the V2 frontend country picker.

        By default ``product_only=True`` so the panel shows US/AU/GB/DE/FR.
        Non-product legacy rows (ID/VN/PH/…) are purged on load.
        """
        await self.ensure_product_countries()

        query = select(VisaCountry).order_by(
            VisaCountry.display_order.asc(),
            VisaCountry.country_code.asc(),
        )
        if enabled is not None:
            query = query.where(VisaCountry.enabled == enabled)
        if product_only:
            product_codes = sorted(
                {
                    normalize_destination_code(c)
                    for c in PRODUCT_DESTINATION_CODES
                }
            )
            # Include UK alias if present in DB
            codes = set(product_codes) | {"UK"}
            query = query.where(VisaCountry.country_code.in_(codes))

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        return {
            "items": [self._serialize_country(r) for r in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        }

    async def create_country(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new country entry."""
        code = normalize_destination_code(data["country_code"])
        if code in {
            normalize_destination_code(c) for c in PRODUCT_DESTINATION_CODES
        } | {"UK"}:
            data = {**data, "country_code": "GB" if code == "UK" else code}
        else:
            from app.core.product_scope import NON_PRODUCT_DESTINATION_CODES

            if code in NON_PRODUCT_DESTINATION_CODES or code in {"ID", "VN", "PH"}:
                raise BizException(
                    ErrorCode.BAD_REQUEST,
                    message=(
                        f"{code} is not a fileable visa destination "
                        "(customer market only). Use US/AU/GB/DE/FR."
                    ),
                )

        existing = await self.db.scalar(
            select(VisaCountry).where(VisaCountry.country_code == data["country_code"])
        )
        if existing is not None:
            raise BizException(
                ErrorCode.CONFLICT, message="Country code already exists"
            )

        visa_types = None
        if data.get("visa_types"):
            visa_types = json.dumps(data["visa_types"])

        country = VisaCountry(
            country_code=data["country_code"],
            country_name_zh=data["country_name_zh"],
            country_name_en=data["country_name_en"],
            enabled=data.get("enabled", True),
            display_order=data.get("display_order", 0),
            base_url=data.get("base_url"),
            form_path=data.get("form_path"),
            form_template_url=data.get("form_template_url"),
            rpa_config=data.get("rpa_config"),
            visa_types=visa_types,
            fee_usd=data.get("fee_usd"),
            processing_days=data.get("processing_days"),
            description=data.get("description"),
            flag_emoji=data.get("flag_emoji"),
            capital_city=data.get("capital_city"),
            extra=data.get("extra"),
        )
        self.db.add(country)
        await self.db.flush()
        await self._sync_destination_enabled(country.country_code, country.enabled)
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.country.create",
            target_type="country",
            target_id=country.id,
        )
        await self.db.commit()
        await self.db.refresh(country)
        return self._serialize_country(country)

    async def update_country(self, country_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """Update country fields (partial update)."""
        country = await self.db.get(VisaCountry, country_id)
        if country is None:
            raise BizException(ErrorCode.NOT_FOUND, message="Country not found")

        if "country_name_zh" in data:
            country.country_name_zh = data["country_name_zh"]
        if "country_name_en" in data:
            country.country_name_en = data["country_name_en"]
        if "enabled" in data and data["enabled"] is not None:
            country.enabled = data["enabled"]
        if "display_order" in data and data["display_order"] is not None:
            country.display_order = data["display_order"]
        if "base_url" in data:
            country.base_url = data["base_url"]
        if "form_path" in data:
            country.form_path = data["form_path"]
        if "form_template_url" in data:
            country.form_template_url = data["form_template_url"]
        if "rpa_config" in data:
            country.rpa_config = data["rpa_config"]
        if "visa_types" in data:
            country.visa_types = (
                json.dumps(data["visa_types"]) if data["visa_types"] else None
            )
        if "fee_usd" in data:
            country.fee_usd = data["fee_usd"]
        if "processing_days" in data:
            country.processing_days = data["processing_days"]
        if "description" in data:
            country.description = data["description"]
        if "flag_emoji" in data:
            country.flag_emoji = data["flag_emoji"]
        if "capital_city" in data:
            country.capital_city = data["capital_city"]
        if "extra" in data:
            country.extra = data["extra"]

        if "enabled" in data and data["enabled"] is not None:
            await self._sync_destination_enabled(country.country_code, country.enabled)

        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.country.update",
            target_type="country",
            target_id=country_id,
            payload={"updated_fields": sorted([k for k in data.keys() if data.get(k) is not None])},
        )
        await self.db.commit()
        await self.db.refresh(country)
        return self._serialize_country(country)

    async def delete_country(self, country_id: int) -> None:
        """Soft-delete: set enabled=False (offline, not removed from DB)."""
        country = await self.db.get(VisaCountry, country_id)
        if country is None:
            raise BizException(ErrorCode.NOT_FOUND, message="Country not found")
        country.enabled = False
        await self._sync_destination_enabled(country.country_code, False)
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.country.delete",
            target_type="country",
            target_id=country_id,
        )
        await self.db.commit()

    async def toggle_country(self, country_id: int, enabled: bool) -> dict[str, Any]:
        """Toggle the V2 enabled flag without re-sending the whole record.

        Returns the updated country (V2 schema). The audit trail records
        ``admin.country.toggle`` so operators can tell a toggle apart from
        a generic update in the log. Also syncs ``visa_destinations.enabled``
        so the public picker and order create guard stay in lockstep.
        """
        country = await self.db.get(VisaCountry, country_id)
        if country is None:
            raise BizException(ErrorCode.NOT_FOUND, message="Country not found")
        old = country.enabled
        country.enabled = enabled
        await self._sync_destination_enabled(country.country_code, enabled)
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.country.toggle",
            target_type="country",
            target_id=country_id,
            payload={"from": old, "to": enabled},
        )
        await self.db.commit()
        await self.db.refresh(country)
        return self._serialize_country(country)

    async def reorder_countries(self, orders: list[dict[str, Any]]) -> dict[str, Any]:
        """Bulk-update display_order for the supplied country ids.

        Implementation notes:
          * Validates every id exists up-front (single batched query) so we
            don't half-commit when the payload is malformed.
          * One UPDATE per id inside the same transaction — safer than a
            bulk CASE WHEN for small N (typical: < 30 countries).
          * Returns the refreshed, ordered list so the UI can re-render
            without a second round-trip.
        """
        if not orders:
            raise BizException(ErrorCode.BAD_REQUEST, message="orders is empty")

        ids = [int(item["id"]) for item in orders]
        # De-dup — the UI sometimes drops an id twice in the payload.
        ids_unique = list(dict.fromkeys(ids))

        existing_rows = (
            await self.db.execute(
                select(VisaCountry).where(VisaCountry.id.in_(ids_unique))
            )
        ).scalars().all()
        existing_by_id: dict[int, VisaCountry] = {r.id: r for r in existing_rows}

        missing = [cid for cid in ids_unique if cid not in existing_by_id]
        if missing:
            raise BizException(
                ErrorCode.NOT_FOUND,
                message=f"Country ids not found: {missing}",
            )

        for item in orders:
            country = existing_by_id[int(item["id"])]
            country.display_order = int(item["display_order"])

        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.country.reorder",
            target_type="country",
            target_id=0,
            payload={"orders": [{"id": int(it["id"]), "display_order": int(it["display_order"])} for it in orders]},
        )
        await self.db.commit()

        # Re-fetch ordered list (full, no pagination — typical N < 30).
        rows = (
            await self.db.execute(
                select(VisaCountry).order_by(
                    VisaCountry.display_order.asc(),
                    VisaCountry.country_code.asc(),
                )
            )
        ).scalars().all()
        return {
            "updated": len(orders),
            "items": [self._serialize_country(r) for r in rows],
        }

    # ------------------------------------------------------------------ #
    # Validation rules                                                      #
    # ------------------------------------------------------------------ #
    async def get_validation_rules(self) -> list[dict[str, Any]]:
        """Return all rules as a list of dicts.

        W21.3 fix: params 是 JSON 字符串 (跟 DB 一致), 不要 json.loads,
        ValidationRuleOut.params 期望 str 不是 dict.
        """
        rows = (
            await self.db.execute(select(ValidationRule).order_by(ValidationRule.code))
        ).scalars().all()
        return [
            {
                "id": r.id,
                "code": r.code,
                "rule_type": r.rule_type,
                "severity": r.severity,
                "message_key": r.message_key,
                "params": r.params,
                "enabled": r.enabled,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]

    async def update_validation_rules(
        self, rules: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Upsert validation rules: insert new codes, update existing ones.

        Performance fix: batch-load all existing rules in one query, then
        diff in Python. Previously made N separate db.scalar() calls (one per
        rule in the input list), an O(N) N+1 pattern. Now uses 1 batch query +
        1 INSERT per new rule — O(N) total with no per-iteration DB round-trips.
        """
        # 1) Batch-load all existing rules whose codes appear in the input.
        #    One query instead of N individual lookups.
        codes = [r["code"] for r in rules]
        existing_rows = (
            await self.db.execute(
                select(ValidationRule).where(ValidationRule.code.in_(codes))
            )
        ).scalars().all()
        existing_by_code: dict[str, ValidationRule] = {
            r.code: r for r in existing_rows
        }

        # 2) Upsert: update in-place, queue inserts for new codes.
        for rule in rules:
            code = rule["code"]
            existing = existing_by_code.get(code)
            if existing:
                existing.rule_type = rule.get("rule_type", existing.rule_type)
                existing.severity = rule.get("severity", existing.severity)
                existing.message_key = rule.get("message_key", existing.message_key)
                existing.params = (
                    json.dumps(rule["params"]) if "params" in rule else existing.params
                )
                existing.enabled = rule.get("enabled", existing.enabled)
            else:
                new_rule = ValidationRule(
                    code=code,
                    rule_type=rule.get("rule_type", "unknown"),
                    severity=rule.get("severity", "error"),
                    message_key=rule.get("message_key", code),
                    params=json.dumps(rule["params"]) if "params" in rule else None,
                    enabled=rule.get("enabled", True),
                )
                self.db.add(new_rule)

        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.validation_rules.update",
        )
        await self.db.commit()
        return await self.get_validation_rules()

    # ------------------------------------------------------------------ #
    # RPA config                                                            #
    # ------------------------------------------------------------------ #
    def _rpa_config_path(self) -> Path:
        return Path(self.settings.log_dir).parent / "data" / "rpa_config.yaml"

    # Default RPA config — used when YAML file missing (CI / first run)
    _DEFAULT_RPA_CONFIG: dict[str, Any] = {
        "rate_limits": {"requests_per_minute": 30, "burst": 5},
        "timeouts": {"page_load_ms": 15000, "submit_ms": 30000},
        "retry": {"max_attempts": 3, "backoff_seconds": 5},
        "captcha": {"provider": "mock", "timeout_seconds": 60},
        "session": {"cookie_ttl_seconds": 3600, "user_agent_pool": []},
        "countries": {},
        "mock_mode": True,
    }

    def get_rpa_config(self) -> dict[str, Any]:
        """Load RPA config from YAML file, merged over defaults.

        W21.3 fix: return full default config (not empty dict) when YAML missing,
        so Pydantic RpaConfigOut validation doesn't fail.
        """
        path = self._rpa_config_path()
        config: dict[str, Any] = dict(self._DEFAULT_RPA_CONFIG)
        if not path.exists():
            return config
        try:
            import yaml

            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            # Merge: defaults < yaml overrides
            for key, value in loaded.items():
                if value is not None:
                    config[key] = value
            return config
        except Exception:
            return config

    async def update_rpa_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Merge updates into RPA YAML and write back."""
        import yaml

        path = self._rpa_config_path()
        current = self.get_rpa_config()
        # Deep merge
        for key, value in updates.items():
            if value is not None:
                current[key] = value

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(current, f, allow_unicode=True, sort_keys=False)

        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.rpa_config.update",
        )
        return current

    # ------------------------------------------------------------------ #
    # RPA realtime stats                                                    #
    # ------------------------------------------------------------------ #
    def get_rpa_stats(self) -> dict[str, Any]:
        """Compute realtime RPA pipeline stats from the in-memory scheduler.

        Returns:
          - today_visits:     IP visits since 00:00 UTC (summed across IPs)
          - queued_tasks:     Tasks currently in IDLE / SUBMITTING / WAITING
          - failure_rate_24h: failed / total over the last 24h (0.0 if no terminal)
          - success_count_24h: tasks that hit DONE in last 24h
          - failed_count_24h:  tasks that hit FAILED in last 24h
          - total_count_24h:   terminal tasks in last 24h (DONE+FAILED+CANCELLED)
          - active_accounts:   accounts with at least one running task
          - generated_at:      server-side timestamp (UTC)

        The scheduler holds tasks in memory; we read a snapshot under its
        lock-equivalent (the dict is single-threaded in this MVP).
        """
        scheduler, TaskStatus = _get_rpa_scheduler_singleton()
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        window_start = now - timedelta(hours=24)

        # IP visits today (sum across all tracked IPs)
        today_visits = 0
        for visits in scheduler._ip_visits.values():
            today_visits += sum(1 for v in visits if v >= today_start)

        # Active queue = tasks not in a terminal state
        queued_states = {TaskStatus.IDLE, TaskStatus.SUBMITTING, TaskStatus.WAITING}
        queued_tasks = 0
        success_24h = 0
        failed_24h = 0
        terminal_24h = 0
        active_uids: set[str] = set()
        for task in scheduler._tasks.values():
            if task.status in queued_states:
                queued_tasks += 1
                if getattr(task, "user_id", None):
                    active_uids.add(task.user_id)
            # completed_at is set on terminal transition
            completed = task.completed_at
            if completed is None:
                continue
            # completed_at is naive UTC (per scheduler)
            if completed >= window_start:
                terminal_24h += 1
                if task.status == TaskStatus.DONE:
                    success_24h += 1
                elif task.status == TaskStatus.FAILED:
                    failed_24h += 1

        if terminal_24h > 0:
            failure_rate = round(failed_24h / terminal_24h, 4)
        else:
            failure_rate = 0.0

        return {
            "today_visits": int(today_visits),
            "queued_tasks": int(queued_tasks),
            "failure_rate_24h": float(failure_rate),
            "success_count_24h": int(success_24h),
            "failed_count_24h": int(failed_24h),
            "total_count_24h": int(terminal_24h),
            "active_accounts": len(active_uids),
            "sample_window_seconds": 86400,
            "generated_at": now,
        }

    # ------------------------------------------------------------------ #
    # Dashboard stats (in-memory TTL cache)                               #
    # ------------------------------------------------------------------ #
    _dashboard_cache:Optional[dict[str, Any]]= None
    _dashboard_cache_ttl: float = 60.0  # seconds

    async def get_dashboard_stats(self) -> dict[str, Any]:
        """Return aggregated dashboard metrics, served from a 60-second TTL cache.

        Metrics:
          - today_new_orders  : COUNT(*) WHERE created_at >= today 00:00 UTC
          - week_new_orders   : COUNT(*) WHERE created_at >= Monday 00:00 UTC
          - pending_orders    : COUNT(*) WHERE status IN ('created', 'submitted')
          - completed_orders  : COUNT(*) WHERE status IN ('approved', 'closed')
          - payment_success_rate: orders with paid_at NOT NULL / total orders
          - generated_at      : UTC now
          - cached            : whether the response came from cache
        """
        now = datetime.utcnow()
        cache_key = "dashboard_stats"

        # Check cache
        cached = False
        if (
            AdminService._dashboard_cache is not None
            and AdminService._dashboard_cache.get("_ts", 0)
            + AdminService._dashboard_cache_ttl
            > now.timestamp()
        ):
            result = dict(AdminService._dashboard_cache)
            result["generated_at"] = now
            result["cached"] = True
            return result

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())

        # Direct await (was: asyncio.new_event_loop + run_until_complete which raises
        # RuntimeError when called inside a running event loop)
        stats = await self._fetch_dashboard_stats(today_start, week_start)

        stats["generated_at"] = now
        stats["cached"] = False

        # Cache result
        AdminService._dashboard_cache = dict(stats)
        AdminService._dashboard_cache["_ts"] = now.timestamp()

        return stats

    async def _fetch_dashboard_stats(
        self, today_start: datetime, week_start: datetime
    ) -> dict[str, Any]:
        """Execute the five COUNT/SUM aggregate queries against the DB."""
        pending_statuses = ("created", "paid", "submitted")
        completed_statuses = ("completed", "approved", "closed")

        # today_new_orders
        q_today = select(func.count()).select_from(Order).where(
            Order.created_at >= today_start
        )
        today_new = (await self.db.execute(q_today)).scalar() or 0

        # week_new_orders
        q_week = select(func.count()).select_from(Order).where(
            Order.created_at >= week_start
        )
        week_new = (await self.db.execute(q_week)).scalar() or 0

        # pending_orders
        q_pending = select(func.count()).select_from(Order).where(
            Order.status.in_(pending_statuses)
        )
        pending = (await self.db.execute(q_pending)).scalar() or 0

        # completed_orders
        q_completed = select(func.count()).select_from(Order).where(
            Order.status.in_(completed_statuses)
        )
        completed = (await self.db.execute(q_completed)).scalar() or 0

        # payment_success_rate: orders with paid_at not null / total
        q_total = select(func.count()).select_from(Order)
        total_orders = (await self.db.execute(q_total)).scalar() or 0
        q_paid = select(func.count()).select_from(Order).where(
            Order.paid_at.isnot(None)
        )
        paid_orders = (await self.db.execute(q_paid)).scalar() or 0

        payment_rate = paid_orders / total_orders if total_orders > 0 else 0.0

        return {
            "today_new_orders": today_new,
            "week_new_orders": week_new,
            "pending_orders": pending,
            "completed_orders": completed,
            "payment_success_rate": payment_rate,
        }

    # ------------------------------------------------------------------ #
    # Audit logs                                                           #
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    # Payment flow (资金流)                                                #
    # ------------------------------------------------------------------ #
    async def list_payments(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        refund_status: Optional[str] = None,
    ) -> dict[str, Any]:
        """资金流分页列表：扫描所有有 extra["payment"] 的订单。

        支持按支付状态 (extra.payment.status) 或退款副轨 (orders.refund_status) 筛选。
        """
        query = (
            select(Order)
            .where(Order.extra.isnot(None))
            .order_by(Order.created_at.desc())
        )
        if refund_status:
            query = query.where(Order.refund_status == refund_status)
        rows = (await self.db.execute(query)).scalars().all()

        all_items: list[dict[str, Any]] = []
        stats = {
            "total_count": 0,
            "total_amount_cents": 0,
            "paid_count": 0,
            "pending_count": 0,
            "refund_pending_count": 0,
            "refund_approved_count": 0,
            "refund_completed_count": 0,
            "refund_failed_count": 0,
        }
        for order in rows:
            extra = {}
            try:
                extra = json.loads(order.extra) if isinstance(order.extra, str) else (order.extra or {})
            except Exception:
                pass
            payment = extra.get("payment") or {}
            pay_status = payment.get("status") or "none"
            rs = order.refund_status or "none"

            if status and pay_status != status:
                continue

            amount_cents = int(payment.get("amount_cents") or 0)
            stats["total_count"] += 1
            stats["total_amount_cents"] += amount_cents
            if pay_status == "paid":
                stats["paid_count"] += 1
            if pay_status == "pending":
                stats["pending_count"] += 1
            if rs == "pending":
                stats["refund_pending_count"] += 1
            elif rs == "approved":
                stats["refund_approved_count"] += 1
            elif rs == "completed":
                stats["refund_completed_count"] += 1
            elif rs == "failed":
                stats["refund_failed_count"] += 1

            all_items.append({
                "order_id": order.id,
                "order_no": order.order_no,
                "user_id": order.user_id,
                "trade_no": payment.get("trade_no"),
                "status": pay_status,
                "order_status": order.status,
                "refund_status": rs,
                "refund_amount": float(order.refund_amount) if order.refund_amount is not None else None,
                "amount_cents": amount_cents,
                "currency": payment.get("currency") or "USD",
                "paid_at": _parse_iso(payment.get("paid_at")) or order.paid_at,
                "refunded_at": order.refunded_at or _parse_iso(payment.get("refunded_at")),
                "created_at": order.created_at,
                "updated_at": order.updated_at,
            })

        total = len(all_items)
        offset = (page - 1) * page_size
        items = all_items[offset:offset + page_size]

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
            "stats": stats,
        }

    # ------------------------------------------------------------------ #
    # Audit logs (W35 扩展)                                                #
    # ------------------------------------------------------------------ #
    async def list_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        action: Optional[str] = None,
        actor_type: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Paginated audit log list with extended filters.

        Filters:
          - action       : LIKE 'action%' (e.g. 'order' → order.create, order.update...)
          - actor_type   : exact (user / admin / system / rpa)
          - target_type  : exact (order / user / country / admin_user / i18n_override)
          - target_id    : exact
          - start_time   : created_at >= start_time
          - end_time     : created_at <= end_time

        Returns items with `actor_name` / `target_name` resolved by joining
        users / admin_users / orders / countries tables where possible.
        """
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if action:
            query = query.where(AuditLog.action.like(f"{action}%"))
        if actor_type:
            query = query.where(AuditLog.actor_type == actor_type)
        if target_type:
            query = query.where(AuditLog.target_type == target_type)
        if target_id is not None:
            query = query.where(AuditLog.target_id == target_id)
        if start_time:
            query = query.where(AuditLog.created_at >= start_time)
        if end_time:
            query = query.where(AuditLog.created_at <= end_time)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        items = [self._serialize_log_row(r) for r in rows]
        await self._resolve_log_names(items)

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        }

    async def get_log(self, log_id: int) -> dict[str, Any]:
        """单条日志详情 — payload 解析为 dict 后一并返回."""
        row = await self.db.get(AuditLog, log_id)
        if row is None:
            raise BizException(ErrorCode.NOT_FOUND, message="Audit log not found")
        item = self._serialize_log_row(row)
        await self._resolve_log_names([item])
        payload_json = None
        if row.payload:
            try:
                payload_json = json.loads(row.payload)
            except Exception:
                payload_json = row.payload
        item["payload_json"] = payload_json
        return item

    async def list_log_filters(self) -> dict[str, Any]:
        """返回所有出现过的 action / actor_type / target_type 列表(用于筛选下拉)."""
        action_rows = (
            await self.db.execute(
                select(AuditLog.action).group_by(AuditLog.action).order_by(AuditLog.action)
            )
        ).scalars().all()
        actor_rows = (
            await self.db.execute(
                select(AuditLog.actor_type).group_by(AuditLog.actor_type).order_by(AuditLog.actor_type)
            )
        ).scalars().all()
        target_rows = (
            await self.db.execute(
                select(AuditLog.target_type)
                .where(AuditLog.target_type.isnot(None))
                .group_by(AuditLog.target_type)
                .order_by(AuditLog.target_type)
            )
        ).scalars().all()
        return {
            "actions": list(action_rows),
            "actor_types": list(actor_rows),
            "target_types": list(t for t in target_rows if t),
        }

    def _serialize_log_row(self, r: AuditLog) -> dict[str, Any]:
        return {
            "id": r.id,
            "uuid": r.uuid,
            "actor_type": r.actor_type,
            "actor_id": r.actor_id,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "payload": r.payload,
            "created_at": r.created_at,
            "actor_name": None,
            "target_name": None,
        }

    async def _resolve_log_names(self, items: list[dict[str, Any]]) -> None:
        """批量 join users / admin_users / orders 表, 给 actor_name / target_name 填值.

        为避免 N+1, 按 actor_type + actor_id / target_type + target_id 批量 fetch.
        """
        if not items:
            return
        # Collect IDs by category
        user_ids: set[int] = set()
        admin_ids: set[int] = set()
        order_ids: set[int] = set()
        country_ids: set[int] = set()
        i18n_ids: set[int] = set()

        for it in items:
            if it["actor_type"] == "user" and it["actor_id"]:
                user_ids.add(int(it["actor_id"]))
            elif it["actor_type"] == "admin" and it["actor_id"]:
                admin_ids.add(int(it["actor_id"]))
            if it["target_type"] == "order" and it["target_id"]:
                order_ids.add(int(it["target_id"]))
            elif it["target_type"] == "country" and it["target_id"]:
                country_ids.add(int(it["target_id"]))
            elif it["target_type"] == "i18n_override" and it["target_id"]:
                i18n_ids.add(int(it["target_id"]))

        user_map: dict[int, str] = {}
        if user_ids:
            rows = (
                await self.db.execute(select(User.id, User.email, User.nickname).where(User.id.in_(user_ids)))
            ).all()
            for uid, email, nick in rows:
                user_map[uid] = (nick or email or f"#{uid}")[:32]

        admin_map: dict[int, str] = {}
        if admin_ids:
            rows = (
                await self.db.execute(
                    select(AdminUser.id, AdminUser.username).where(AdminUser.id.in_(admin_ids))
                )
            ).all()
            for aid, name in rows:
                admin_map[aid] = name or f"#{aid}"

        order_map: dict[int, str] = {}
        if order_ids:
            rows = (
                await self.db.execute(
                    select(Order.id, Order.order_no).where(Order.id.in_(order_ids))
                )
            ).all()
            for oid, ono in rows:
                order_map[oid] = ono

        country_map: dict[int, str] = {}
        if country_ids:
            rows = (
                await self.db.execute(
                    select(VisaCountry.id, VisaCountry.country_code, VisaCountry.country_name_en)
                    .where(VisaCountry.id.in_(country_ids))
                )
            ).all()
            for cid, code, name_en in rows:
                country_map[cid] = f"{code} · {name_en}" if code else (name_en or f"#{cid}")

        i18n_map: dict[int, str] = {}
        if i18n_ids:
            rows = (
                await self.db.execute(
                    select(I18nOverride.id, I18nOverride.locale, I18nOverride.key)
                    .where(I18nOverride.id.in_(i18n_ids))
                )
            ).all()
            for iid, loc, k in rows:
                i18n_map[iid] = f"{loc}:{k}"

        for it in items:
            if it["actor_type"] == "user" and it["actor_id"]:
                it["actor_name"] = user_map.get(int(it["actor_id"]))
            elif it["actor_type"] == "admin" and it["actor_id"]:
                it["actor_name"] = admin_map.get(int(it["actor_id"]))
            elif it["actor_type"] == "system":
                it["actor_name"] = "system"
            elif it["actor_type"] == "rpa":
                it["actor_name"] = "rpa"
            if it["target_type"] == "order" and it["target_id"]:
                it["target_name"] = order_map.get(int(it["target_id"]))
            elif it["target_type"] == "country" and it["target_id"]:
                it["target_name"] = country_map.get(int(it["target_id"]))
            elif it["target_type"] == "i18n_override" and it["target_id"]:
                it["target_name"] = i18n_map.get(int(it["target_id"]))
            elif it["target_type"] == "user" and it["target_id"]:
                it["target_name"] = user_map.get(int(it["target_id"]))
            elif it["target_type"] == "admin_user" and it["target_id"]:
                it["target_name"] = admin_map.get(int(it["target_id"]))

    # ------------------------------------------------------------------ #
    # i18n overrides (V0 §4.4.4 多语种文案统一管理)                         #
    # ------------------------------------------------------------------ #
    SUPPORTED_LOCALES = {"zh-CN", "en", "vi", "id"}

    async def list_i18n_overrides(
        self,
        page: int = 1,
        page_size: int = 50,
        locale: Optional[str] = None,
        key: Optional[str] = None,
    ) -> dict[str, Any]:
        """分页文案覆盖列表 — 支持 locale / key 模糊搜索."""
        query = select(I18nOverride).order_by(
            I18nOverride.locale.asc(), I18nOverride.key.asc()
        )
        if locale:
            query = query.where(I18nOverride.locale == locale)
        if key:
            query = query.where(I18nOverride.key.like(f"%{key}%"))

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        return {
            "items": [
                {
                    "id": r.id,
                    "locale": r.locale,
                    "key": r.key,
                    "value": r.value,
                    "original_value": r.original_value,
                    "updated_by_admin_id": r.updated_by_admin_id,
                    "updated_at": r.updated_at,
                    "created_at": r.created_at,
                }
                for r in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        }

    async def create_i18n_override(
        self,
        locale: str,
        key: str,
        value: str,
        original_value: Optional[str],
        admin_id: int,
    ) -> dict[str, Any]:
        """新建覆盖 — 同 locale+key 已存在则抛 CONFLICT."""
        if locale not in self.SUPPORTED_LOCALES:
            raise BizException(ErrorCode.BAD_REQUEST, message=f"Unsupported locale: {locale}")
        existing = (
            await self.db.execute(
                select(I18nOverride).where(
                    I18nOverride.locale == locale, I18nOverride.key == key
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise BizException(
                ErrorCode.CONFLICT,
                message=f"Override already exists for {locale}:{key}",
            )
        row = I18nOverride(
            locale=locale,
            key=key,
            value=value,
            original_value=original_value,
            updated_by_admin_id=admin_id,
        )
        self.db.add(row)
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=admin_id,
            action="admin.i18n.create",
            target_type="i18n_override",
            target_id=0,
            payload={"locale": locale, "key": key},
        )
        await self.db.commit()
        await self.db.refresh(row)
        return {
            "id": row.id,
            "locale": row.locale,
            "key": row.key,
            "value": row.value,
            "original_value": row.original_value,
            "updated_by_admin_id": row.updated_by_admin_id,
            "updated_at": row.updated_at,
            "created_at": row.created_at,
        }

    async def update_i18n_override(
        self, override_id: int, data: dict[str, Any], admin_id: int
    ) -> dict[str, Any]:
        """更新覆盖 — 可改 value 或 original_value."""
        row = await self.db.get(I18nOverride, override_id)
        if row is None:
            raise BizException(ErrorCode.NOT_FOUND, message="Override not found")
        if "value" in data and data["value"] is not None:
            row.value = data["value"]
        if "original_value" in data:
            row.original_value = data["original_value"]
        row.updated_by_admin_id = admin_id
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=admin_id,
            action="admin.i18n.update",
            target_type="i18n_override",
            target_id=override_id,
            payload={"locale": row.locale, "key": row.key},
        )
        await self.db.commit()
        await self.db.refresh(row)
        return {
            "id": row.id,
            "locale": row.locale,
            "key": row.key,
            "value": row.value,
            "original_value": row.original_value,
            "updated_by_admin_id": row.updated_by_admin_id,
            "updated_at": row.updated_at,
            "created_at": row.created_at,
        }

    async def delete_i18n_override(self, override_id: int, admin_id: int) -> None:
        """删除覆盖 — 恢复使用前端内置 json 文案."""
        row = await self.db.get(I18nOverride, override_id)
        if row is None:
            raise BizException(ErrorCode.NOT_FOUND, message="Override not found")
        locale, key = row.locale, row.key
        await self.db.delete(row)
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=admin_id,
            action="admin.i18n.delete",
            target_type="i18n_override",
            target_id=override_id,
            payload={"locale": locale, "key": key},
        )
        await self.db.commit()

    async def import_i18n_overrides(
        self, locale: str, entries: dict[str, str], admin_id: int
    ) -> dict[str, Any]:
        """批量导入 — 已存在的 (locale, key) 更新 value; 不存在的创建.

        返回统计: {created: N, updated: M, skipped: K}
        """
        if locale not in self.SUPPORTED_LOCALES:
            raise BizException(ErrorCode.BAD_REQUEST, message=f"Unsupported locale: {locale}")

        # Batch-load all existing keys for this locale
        existing_rows = (
            await self.db.execute(
                select(I18nOverride).where(I18nOverride.locale == locale)
            )
        ).scalars().all()
        existing_by_key = {r.key: r for r in existing_rows}

        created = 0
        updated = 0
        skipped = 0
        for key, value in entries.items():
            if not key or value is None:
                skipped += 1
                continue
            row = existing_by_key.get(key)
            if row:
                if row.value != value:
                    row.value = value
                    row.updated_by_admin_id = admin_id
                    updated += 1
                else:
                    skipped += 1
            else:
                self.db.add(
                    I18nOverride(
                        locale=locale,
                        key=key,
                        value=value,
                        updated_by_admin_id=admin_id,
                    )
                )
                created += 1

        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=admin_id,
            action="admin.i18n.import",
            target_type="i18n_override",
            target_id=0,
            payload={
                "locale": locale,
                "created": created,
                "updated": updated,
                "skipped": skipped,
            },
        )
        await self.db.commit()
        return {
            "locale": locale,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "total_in_payload": len(entries),
        }

    async def export_i18n_overrides(self, locale: str) -> dict[str, Any]:
        """导出该 locale 全部覆盖为 JSON-friendly dict."""
        if locale not in self.SUPPORTED_LOCALES:
            raise BizException(ErrorCode.BAD_REQUEST, message=f"Unsupported locale: {locale}")
        rows = (
            await self.db.execute(
                select(I18nOverride)
                .where(I18nOverride.locale == locale)
                .order_by(I18nOverride.key)
            )
        ).scalars().all()
        entries = {r.key: r.value for r in rows}
        return {
            "locale": locale,
            "count": len(entries),
            "entries": entries,
        }

    # ------------------------------------------------------------------ #
    # Role management (W34)                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _serialize_role(r: AdminRole) -> dict[str, Any]:
        return {
            "id": r.id, "name": r.name, "code": r.code,
            "permissions": r.permissions or [],
            "description": r.description, "is_active": r.is_active,
            "created_at": r.created_at, "updated_at": r.updated_at,
        }

    async def list_roles(self) -> list[dict[str, Any]]:
        """返回所有角色（不含敏感信息）"""
        rows = (
            await self.db.execute(
                select(AdminRole).where(AdminRole.is_active == True).order_by(AdminRole.id)  # noqa: E712
            )
        ).scalars().all()
        return [self._serialize_role(r) for r in rows]

    async def create_role(self, data: dict[str, Any]) -> dict[str, Any]:
        """创建角色 — code 必须唯一"""
        existing = (
            await self.db.execute(select(AdminRole).where(AdminRole.code == data["code"]))
        ).scalar_one_or_none()
        if existing:
            raise BizException(ErrorCode.CONFLICT, message="角色代码已存在")
        role = AdminRole(
            name=data["name"],
            code=data["code"],
            permissions=data.get("permissions") or [],
            description=data.get("description"),
            is_active=True,
        )
        self.db.add(role)
        await record_audit(
            self.db, actor_type="admin", actor_id=0,
            action="admin.role.create", target_type="admin_role", target_id=0,
            payload={"code": data["code"]},
        )
        await self.db.commit()
        await self.db.refresh(role)
        return self._serialize_role(role)

    async def update_role(self, role_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """更新角色（description / permissions / is_active）"""
        role = await self.db.get(AdminRole, role_id)
        if not role:
            raise BizException(ErrorCode.NOT_FOUND, message="角色不存在")
        if "description" in data:
            role.description = data["description"]
        if "permissions" in data and data["permissions"] is not None:
            role.permissions = data["permissions"]
        if "is_active" in data and data["is_active"] is not None:
            role.is_active = data["is_active"]
        await record_audit(
            self.db, actor_type="admin", actor_id=0,
            action="admin.role.update", target_type="admin_role", target_id=role_id,
            payload={"updated_fields": list(data.keys())},
        )
        await self.db.commit()
        await self.db.refresh(role)
        return self._serialize_role(role)

    async def delete_role(self, role_id: int) -> None:
        """停用角色（soft-delete: is_active=False）。super_admin 角色不可停用。"""
        role = await self.db.get(AdminRole, role_id)
        if not role:
            raise BizException(ErrorCode.NOT_FOUND, message="角色不存在")
        if role.code == "super_admin":
            raise BizException(ErrorCode.FORBIDDEN, message="超级管理员角色不可停用")
        role.is_active = False
        await record_audit(
            self.db, actor_type="admin", actor_id=0,
            action="admin.role.delete", target_type="admin_role", target_id=role_id,
        )
        await self.db.commit()

    async def list_admin_users(self, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        """分页管理员列表"""
        query = (
            select(AdminUser)
            .options(selectinload(AdminUser.role))
            .order_by(AdminUser.created_at.desc())
        )
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        offset = (page - 1) * page_size
        rows = (await self.db.execute(query.offset(offset).limit(page_size))).scalars().all()
        return {
            "items": [
                {
                    "id": u.id, "username": u.username, "role_id": u.role_id,
                    "role_name": u.role.name if u.role else None,
                    "role_code": u.role.code if u.role else None,
                    "permissions": u.role.permissions if u.role else [],
                    "is_active": u.is_active, "created_at": u.created_at,
                    "last_login_at": u.last_login_at,
                }
                for u in rows
            ],
            "page": page, "page_size": page_size, "total": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        }

    async def create_admin_user(self, username: str, password: str, role_id: int) -> dict[str, Any]:
        """创建管理员账号"""
        import bcrypt
        existing = (
            await self.db.execute(select(AdminUser).where(AdminUser.username == username))
        ).scalar_one_or_none()
        if existing:
            raise BizException(ErrorCode.CONFLICT, message="用户名已存在")
        role = await self.db.get(AdminRole, role_id)
        if not role or not role.is_active:
            raise BizException(ErrorCode.NOT_FOUND, message="角色不存在")
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = AdminUser(username=username, password_hash=pw_hash, role_id=role_id)
        self.db.add(user)
        await record_audit(self.db, actor_type="admin", actor_id=0, action="admin.user.create",
                           target_type="admin_user", target_id=0,
                           payload={"username": username, "role_id": role_id})
        await self.db.commit()
        await self.db.refresh(user)
        return {
            "id": user.id, "username": user.username, "role_id": user.role_id,
            "role_name": role.name, "role_code": role.code, "permissions": role.permissions,
            "is_active": user.is_active, "created_at": user.created_at, "last_login_at": user.last_login_at,
        }

    async def update_admin_user(self, user_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """更新管理员账号（密码/角色/状态）"""
        import bcrypt
        user = await self.db.get(AdminUser, user_id)
        if not user:
            raise BizException(ErrorCode.NOT_FOUND, message="用户不存在")
        if "password" in data and data["password"]:
            user.password_hash = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()
        if "role_id" in data and data["role_id"]:
            role = await self.db.get(AdminRole, data["role_id"])
            if not role or not role.is_active:
                raise BizException(ErrorCode.NOT_FOUND, message="角色不存在")
            user.role_id = data["role_id"]
        if "is_active" in data and data["is_active"] is not None:
            user.is_active = data["is_active"]
        await record_audit(self.db, actor_type="admin", actor_id=0, action="admin.user.update",
                           target_type="admin_user", target_id=user_id,
                           payload={"updated_fields": list(data.keys())})
        await self.db.commit()
        role = await self.db.get(AdminRole, user.role_id)
        return {
            "id": user.id, "username": user.username, "role_id": user.role_id,
            "role_name": role.name if role else None, "role_code": role.code if role else None,
            "permissions": role.permissions if role else [],
            "is_active": user.is_active, "created_at": user.created_at, "last_login_at": user.last_login_at,
        }

    async def delete_admin_user(self, user_id: int) -> None:
        """删除管理员（软删除：is_active=False）"""
        user = await self.db.get(AdminUser, user_id)
        if not user:
            raise BizException(ErrorCode.NOT_FOUND, message="用户不存在")
        user.is_active = False
        await record_audit(self.db, actor_type="admin", actor_id=0, action="admin.user.delete",
                           target_type="admin_user", target_id=user_id)
        await self.db.commit()

    # ---- W35: extensions for C 端 users / logs / i18n / countries / rules ----

    async def list_log_actions(self) -> list[str]:
        """Distinct non-empty action strings from audit_log (for filter dropdown)."""
        from sqlalchemy import select
        from app.models.audit_log import AuditLog
        q = select(AuditLog.action).distinct().where(AuditLog.action.isnot(None)).order_by(AuditLog.action)
        rows = (await self.db.execute(q)).scalars().all()
        return [r for r in rows if r]

    async def test_validation_rule(self, rule_code: str, sample_value: Any) -> dict[str, Any]:
        """Evaluate a validation rule against a sample value.

        Rules are loaded from the in-memory store maintained by ValidationRuleService.
        For now (W35) we just look up by rule_code and apply simple operators.
        """
        from app.services.validation_rules import ValidationRuleService
        svc = ValidationRuleService()
        rules = await svc.list_active_rules()
        rule = next((r for r in rules if r.get("code") == rule_code), None)
        if not rule:
            return {"matched": False, "severity": "info", "message": f"rule '{rule_code}' not found"}
        op = rule.get("operator", "eq")
        threshold = rule.get("threshold")
        try:
            matched = _apply_operator(op, sample_value, threshold)
        except Exception as e:
            return {"matched": False, "severity": "error", "message": f"evaluation error: {e}"}
        return {
            "matched": matched,
            "severity": rule.get("severity", "warn") if matched else "info",
            "message": rule.get("error_message_i18n_key") or rule.get("name") or rule_code,
        }

    async def get_validation_rule_history(self, rule_code: str, limit: int = 50) -> list[dict[str, Any]]:
        """Recent audit_log entries that touched this validation rule."""
        from sqlalchemy import select
        from app.models.audit_log import AuditLog
        q = (
            select(AuditLog)
            .where(AuditLog.action.like("validation_rules.%"))
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
        rows = (await self.db.execute(q)).scalars().all()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                payload = json.loads(r.payload) if r.payload else {}
            except Exception:
                payload = {}
            if payload.get("rule_code") == rule_code or rule_code in (r.payload or ""):
                out.append(_audit_row_to_dict(r, payload))
        return out

    async def set_user_status(self, user_id: int, status: str, admin_id: int) -> None:
        from app.models.user import User
        user = await self.db.get(User, user_id)
        if not user:
            raise BizException(ErrorCode.NOT_FOUND, message="用户不存在")
        if status not in {"active", "disabled", "pending_destroy"}:
            raise BizException(ErrorCode.BAD_REQUEST, message=f"invalid status: {status}")
        user.status = status
        await record_audit(
            self.db, actor_type="admin", actor_id=admin_id,
            action=f"user.status.{status}", target_type="user", target_id=user_id,
        )
        await self.db.commit()

    async def update_user_profile(self, user_id: int, payload: dict[str, Any], admin_id: int) -> dict[str, Any]:
        from app.models.user import User
        user = await self.db.get(User, user_id)
        if not user:
            raise BizException(ErrorCode.NOT_FOUND, message="用户不存在")
        allowed = {"nickname", "language_pref", "avatar_url"}
        changed: dict[str, Any] = {}
        for k, v in payload.items():
            if k in allowed and v is not None:
                setattr(user, k, v)
                changed[k] = v
        if changed:
            await record_audit(
                self.db, actor_type="admin", actor_id=admin_id,
                action="user.profile.update", target_type="user", target_id=user_id,
                payload=json.dumps(changed, ensure_ascii=False),
            )
            await self.db.commit()
        return _user_to_dict(user)


def _apply_operator(op: str, value: Any, threshold: Any) -> bool:
    """Tiny rule evaluator used by test_validation_rule."""
    try:
        if op == "exists":
            return value is not None and value != ""
        if op == "eq":
            return value == threshold
        if op == "in":
            return value in (threshold or [])
        if op in {"gt", "gte", "lt", "lte"}:
            v = float(value)
            t = float(threshold)
            if op == "gt": return v > t
            if op == "gte": return v >= t
            if op == "lt": return v < t
            if op == "lte": return v <= t
        if op == "regex":
            import re
            return bool(re.search(str(threshold), str(value or "")))
    except (TypeError, ValueError):
        return False
    return False


def _audit_row_to_dict(r: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r.id,
        "uuid": getattr(r, "uuid", None),
        "actor_type": r.actor_type,
        "actor_id": r.actor_id,
        "action": r.action,
        "target_type": r.target_type,
        "target_id": r.target_id,
        "payload": json.dumps(payload, ensure_ascii=False) if payload else None,
        "ip": getattr(r, "ip", None),
        "ua": getattr(r, "ua", None),
        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
    }


def _user_to_dict(user: Any) -> dict[str, Any]:
    return {
        "id": user.id,
        "uuid": user.uuid,
        "email": user.email,
        "username": user.username,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "language_pref": user.language_pref,
        "status": user.status,
        "mfa_enabled": user.mfa_enabled,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "last_login_ip": user.last_login_ip,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


# --------------------------------------------------------------------------- #
# V2 Dashboard (W37) — KPI / trend / funnel / top countries / alerts            #
# --------------------------------------------------------------------------- #
# 小心 Order.submitted_at 是 None ⇒ 还没提交(支付完成通常也会落 submitted_at);
# total_amount 是 USD(主币种), 其他币种先按 1:1 处理(实际下个迭代再补汇率).
# 时间窗以 UTC 切割, 与 Order.created_at 默认 UTC 一致.
_RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def _pct_change(curr: float, prev: float):
    """涨跌幅百分比 (0.12 = +12%, -0.05 = -5%).

    W63: prev=0 时不要假装 +100%,返 None 让前端走"新"分支。
    - prev=0, curr=0: 无变化 → 0.0
    - prev=0, curr>0: 无对比基线 → None (前端不显箭头,显"新")
    - prev>0: 正常算 (curr-prev)/prev
    """
    if prev == 0:
        return None if curr > 0 else 0.0
    return round((curr - prev) / prev, 4)


    async def _qcount(self, q):
        """SELECT COUNT(*) helper — returns int (0 when no rows)."""
        return int((await self.db.execute(q)).scalar() or 0)

    class AdminDashboardServiceMixin:
        """Mixin-style methods on AdminService — 5 个新 dashboard 接口的业务实现."""

        # ---------- summary (4 张 KPI 卡 + 同期对比) ----------
        async def get_dashboard_summary(self) -> dict[str, Any]:
            """返回今天/本月 KPI + 与上周同期对比. 60s in-memory TTL cache."""
            cache_key = "v2_dashboard_summary"
            cached = getattr(self, cache_key, None)
            now = datetime.utcnow()
            if cached and cached.get("_ts", 0) + 60 > now.timestamp():
                out = dict(cached)
                out["generated_at"] = now.isoformat()
                out["cached"] = True
                return out

            today_0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = today_0.replace(day=1)

            # 上周同期窗口 (用于对比): 长度 1 天, 直接拿昨天 0:00 → 今日 0:00 这段
            yesterday_0 = today_0 - timedelta(days=1)
            last_week_today = today_0 - timedelta(days=7)
            last_week_yesterday = yesterday_0 - timedelta(days=7)

            # 今日指标
            today_orders_q = select(func.count()).select_from(Order).where(Order.created_at >= today_0)
            today_orders = int((await self.db.execute(today_orders_q)).scalar() or 0)

            today_revenue_q = (
                select(func.coalesce(func.sum(Order.total_amount), 0))
                .select_from(Order)
                .where(Order.created_at >= today_0, Order.submitted_at.isnot(None))
            )
            today_revenue = float((await self.db.execute(today_revenue_q)).scalar() or 0)

            today_users_q = select(func.count()).select_from(User).where(User.created_at >= today_0)
            today_new_users = int((await self.db.execute(today_users_q)).scalar() or 0)

            # 今日成功率 = 今日订单里 submitted_at 非空的比例
            if today_orders > 0:
                today_paid_q = (
                    select(func.count()).select_from(Order)
                    .where(Order.created_at >= today_0, Order.submitted_at.isnot(None))
                )
                today_paid = int((await self.db.execute(today_paid_q)).scalar() or 0)
                today_success = today_paid / today_orders
            else:
                today_success = 0.0

            # 上周同期 (单日: last_week_yesterday → last_week_today)
            last_orders = await self._qcount(
                select(func.count()).select_from(Order).where(
                    Order.created_at >= last_week_yesterday,
                    Order.created_at < last_week_today,
                )
            )
            last_revenue = float(
                (await self.db.execute(
                    select(func.coalesce(func.sum(Order.total_amount), 0))
                    .select_from(Order)
                    .where(
                        Order.created_at >= last_week_yesterday,
                        Order.created_at < last_week_today,
                        Order.submitted_at.isnot(None),
                    )
                )).scalar() or 0
            )
            last_users = await self._qcount(
                select(func.count()).select_from(User).where(
                    User.created_at >= last_week_yesterday,
                    User.created_at < last_week_today,
                )
            )

            # 本月 + 待处理 + 总用户
            month_orders = await self._qcount(
                select(func.count()).select_from(Order).where(Order.created_at >= month_start)
            )
            pending_orders = await self._qcount(
                select(func.count()).select_from(Order).where(
                    Order.status.in_(("created", "submitted", "reviewing"))
                )
            )
            total_users = await self._qcount(select(func.count()).select_from(User))

            out = {
                "today_orders": today_orders,
                "today_revenue_usd": round(today_revenue, 2),
                "today_new_users": today_new_users,
                "today_success_rate": round(today_success, 4),
                "delta_orders_pct": _pct_change(today_orders, last_orders),
                "delta_revenue_pct": _pct_change(today_revenue, last_revenue),
                "delta_users_pct": _pct_change(today_new_users, last_users),
                "month_orders": month_orders,
                "total_users": total_users,
                "pending_orders": pending_orders,
                "generated_at": now,
                "cached": False,
            }
            cache_blob = dict(out)
            cache_blob["_ts"] = now.timestamp()
            setattr(self, cache_key, cache_blob)
            return out

        # ---------- trend ----------
        async def get_dashboard_trend(self, metric: str = "orders", range_key: str = "7d") -> dict[str, Any]:
            """N 天 (默认 7) 每日 3 个指标的序列化. 只算 metric 当前指向的曲线, 另两个在 total_* 里. """
            days = _RANGE_DAYS.get(range_key, 7)
            now = datetime.utcnow()
            today_0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start = today_0 - timedelta(days=days - 1)

            # 一次性拉 orders + revenue 聚合 (按 date(created_at) 分桶)
            orders_q = (
                select(
                    func.date(Order.created_at).label("d"),
                    func.count(Order.id).label("c"),
                    func.coalesce(func.sum(Order.total_amount), 0).label("rev"),
                )
                .where(Order.created_at >= start)
                .group_by(func.date(Order.created_at))
            )
            orders_rows = (await self.db.execute(orders_q)).all()
            orders_map = {str(r.d): int(r.c) for r in orders_rows}
            revenue_map = {str(r.d): float(r.rev or 0) for r in orders_rows}

            users_q = (
                select(func.date(User.created_at).label("d"), func.count(User.id).label("c"))
                .where(User.created_at >= start)
                .group_by(func.date(User.created_at))
            )
            users_rows = (await self.db.execute(users_q)).all()
            users_map = {str(r.d): int(r.c) for r in users_rows}

            points = []
            total_orders = 0
            total_revenue = 0.0
            total_users = 0
            for i in range(days):
                day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
                orders = orders_map.get(day, 0)
                revenue = revenue_map.get(day, 0.0)
                users = users_map.get(day, 0)
                total_orders += orders
                total_revenue += revenue
                total_users += users
                points.append({
                    "date": day,
                    "orders": orders,
                    "revenue_usd": round(revenue, 2),
                    "new_users": users,
                })

            return {
                "metric": metric,
                "range": range_key,
                "points": points,
                "total_orders": total_orders,
                "total_revenue_usd": round(total_revenue, 2),
                "total_new_users": total_users,
                "generated_at": now,
            }

        # ---------- funnel ----------
        async def get_dashboard_funnel(self, range_key: str = "7d") -> dict[str, Any]:
            """4 步漏斗: 注册 → 创建订单 → 提交(支付成功) → 当前可统计的最高一步."""
            days = _RANGE_DAYS.get(range_key, 7)
            now = datetime.utcnow()
            start = now - timedelta(days=days)

            async def _count(q):
                return int((await self.db.execute(q)).scalar() or 0)

            # 1) 注册
            register = await _count(
                select(func.count()).select_from(User).where(User.created_at >= start)
            )
            # 兜底: 如果 User 表很空, 看 audit_log user.register
            if register == 0:
                register = await _count(
                    select(func.count()).select_from(AuditLog).where(
                        AuditLog.action == "user.register",
                        AuditLog.created_at >= start,
                    )
                )

            # 2) 创建订单
            create = await _count(
                select(func.count()).select_from(Order).where(Order.created_at >= start)
            )
            # 兜底 audit_log order.create
            if create == 0:
                create = await _count(
                    select(func.count()).select_from(AuditLog).where(
                        AuditLog.action == "order.create",
                        AuditLog.created_at >= start,
                    )
                )

            # 3) 提交订单 (submitted_at 非空 ≈ 已支付)
            submit = await _count(
                select(func.count()).select_from(Order).where(
                    Order.created_at >= start,
                    Order.submitted_at.isnot(None),
                )
            )

            # 4) 走完流程 (approved/closed 成功终态)
            finish = await _count(
                select(func.count()).select_from(Order).where(
                    Order.created_at >= start,
                    Order.status.in_(("approved", "closed")),
                )
            )

            steps = [
                {"key": "register", "label": "注册", "count": register},
                {"key": "order_create", "label": "创建订单", "count": create},
                {"key": "order_submit", "label": "提交订单", "count": submit},
                {"key": "order_finish", "label": "完成 (approved/closed)", "count": finish},
            ]
            # 每步相对上一步的转化率
            for i, s in enumerate(steps):
                if i == 0:
                    s["conversion_pct"] = 100.0
                else:
                    prev = steps[i - 1]["count"]
                    raw_pct = round((s["count"] / prev * 100.0), 2) if prev > 0 else 0.0
                    s["conversion_pct"] = min(100.0, raw_pct)

            overall = min(100.0, round((finish / register * 100.0), 2)) if register > 0 else 0.0

            return {
                "range": range_key,
                "steps": steps,
                "overall_conversion_pct": overall,
                "generated_at": now,
            }

        # ---------- top countries ----------
        async def get_dashboard_top_countries(
            self, range_key: str = "7d", limit: int = 10
        ) -> dict[str, Any]:
            """按 destination_id 分组聚合订单量+营收, join Destination 拿 country_code + 中文名."""
            days = _RANGE_DAYS.get(range_key, 7)
            now = datetime.utcnow()
            start = now - timedelta(days=days)

            rows = (
                await self.db.execute(
                    select(
                        Order.destination_id,
                        func.count(Order.id).label("c"),
                        func.coalesce(func.sum(Order.total_amount), 0).label("rev"),
                    )
                    .where(Order.created_at >= start)
                    .group_by(Order.destination_id)
                    .order_by(func.count(Order.id).desc())
                    .limit(limit)
                )
            ).all()

            if not rows:
                return {"range": range_key, "items": [], "generated_at": now}

            # 取 destination 元数据
            dest_ids = [r.destination_id for r in rows]
            dest_rows = (
                await self.db.execute(
                    select(VisaDestination).where(VisaDestination.id.in_(dest_ids))
                )
            ).scalars().all()
            dest_map = {d.id: d for d in dest_rows}

            # 全期订单总数, 用于算该国家占比
            total = (
                await self.db.execute(
                    select(func.count()).select_from(Order).where(Order.created_at >= start)
                )
            ).scalar() or 0

            items = []
            for r in rows:
                d = dest_map.get(r.destination_id)
                country_code = (d.country_code if d else None) or "--"
                country_name = country_code
                if d and d.country_name_i18n:
                    try:
                        i18n = json.loads(d.country_name_i18n)
                        country_name = (
                            i18n.get("zh-CN") or i18n.get("zh") or i18n.get("en")
                            or country_code
                        )
                    except Exception:
                        country_name = country_code
                items.append({
                    "destination_id": r.destination_id,
                    "country_code": country_code,
                    "country_name": country_name,
                    "order_count": int(r.c),
                    "revenue_usd": round(float(r.rev or 0), 2),
                    "conversion_pct": round(int(r.c) / total * 100.0, 2) if total else 0.0,
                })

            return {
                "range": range_key,
                "items": items,
                "generated_at": now,
            }

        # ---------- alerts ----------
        async def get_dashboard_alerts(self) -> dict[str, Any]:
            """规则式告警: 每条独立判断, 不达阈值不出; 命中即入列. 60s cache."""
            cache_key = "v2_dashboard_alerts"
            cached = getattr(self, cache_key, None)
            now = datetime.utcnow()
            if cached and cached.get("_ts", 0) + 60 > now.timestamp():
                out = {k: v for k, v in cached.items() if k != "_ts"}
                out["generated_at"] = now.isoformat()
                return out

            items = []

            # 1) 待处理订单 > 30 (积压)
            pending_count = int(
                (await self.db.execute(
                    select(func.count()).select_from(Order).where(
                        Order.status.in_(("created", "submitted"))
                    )
                )).scalar() or 0
            )
            if pending_count > 30:
                items.append({
                    "severity": "warning",
                    "code": "pending_orders_high",
                    "title": f"待处理订单积压 ({pending_count})",
                    "detail": "待处理订单超过 30, 建议检查 RPA 队列与人工坐席",
                    "metric_value": pending_count,
                    "threshold": 30.0,
                })

            # 2) enabled 国家 24h 零订单 (但至少有过订单, 否则没意义)
            zero_since = now - timedelta(hours=24)
            active_dests = (
                await self.db.execute(
                    select(VisaDestination).where(VisaDestination.enabled == True)  # noqa: E712
                )
            ).scalars().all()
            if active_dests:
                recent_order_counts = (
                    await self.db.execute(
                        select(
                            Order.destination_id,
                            func.count(Order.id).label("c"),
                        )
                        .where(Order.created_at >= zero_since)
                        .group_by(Order.destination_id)
                    )
                ).all()
                recent_map = {r.destination_id: int(r.c) for r in recent_order_counts}
                zero_dests = [
                    d for d in active_dests
                    if recent_map.get(d.id, 0) == 0 and (d.country_code or "")
                ]
                if zero_dests:
                    names = ", ".join(d.country_code for d in zero_dests[:5])
                    more = len(zero_dests) - 5
                    suffix = f" 等 {more} 个" if more > 0 else ""
                    items.append({
                        "severity": "info",
                        "code": "zero_order_country",
                        "title": f"{len(zero_dests)} 个启用的目的地 24h 零订单",
                        "detail": f"{names}{suffix} 过去 24 小时没有任何新订单",
                        "metric_value": float(len(zero_dests)),
                        "threshold": 0.0,
                    })

            # 3) 失败/异常订单 24h 内过多 (>10)
            fail_count = int(
                (await self.db.execute(
                    select(func.count()).select_from(Order).where(
                        Order.created_at >= zero_since,
                        Order.status.in_(("failed", "abnormal")),
                    )
                )).scalar() or 0
            )
            if fail_count > 10:
                items.append({
                    "severity": "critical",
                    "code": "rpa_failure_spike",
                    "title": f"近 24h 失败/异常订单 {fail_count} 单",
                    "detail": "正常值应 < 5, 请检查 RPA 调度与目标站点可用性",
                    "metric_value": float(fail_count),
                    "threshold": 10.0,
                })

            # 4) 总体支付成功率过低 (< 30%)
            total_orders = int(
                (await self.db.execute(select(func.count()).select_from(Order))).scalar() or 0
            )
            if total_orders > 0:
                paid_orders = int(
                    (await self.db.execute(
                        select(func.count()).select_from(Order).where(
                            Order.submitted_at.isnot(None)
                        )
                    )).scalar() or 0
                )
                overall_rate = paid_orders / total_orders
                if overall_rate < 0.3:
                    items.append({
                        "severity": "warning",
                        "code": "payment_success_low",
                        "title": f"整体支付成功率 {overall_rate*100:.1f}%",
                        "detail": "历史支付成功率低于 30%, 可能影响营收, 建议排查支付链路",
                        "metric_value": round(overall_rate * 100, 2),
                        "threshold": 30.0,
                    })

            out = {"items": items, "generated_at": now}
            cache_blob = dict(out)
            cache_blob["generated_at"] = now
            cache_blob["_ts"] = now.timestamp()
            setattr(self, cache_key, cache_blob)
            return out

# NOTE: V2 dashboard 5 endpoints are now in app/services/admin_dashboard_service.py (W37).
