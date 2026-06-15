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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.middleware.admin_auth import create_admin_token
from app.models.audit_log import AuditLog
from app.models.order import Order, ORDER_STATUSES
from app.models.user import User
from app.models.visa_countries import VisaCountry
from app.models.validation_rules import ValidationRule
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


class AdminService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    # ------------------------------------------------------------------ #
    # Auth                                                                  #
    # ------------------------------------------------------------------ #
    async def login(self, username: str, password: str) -> dict[str, Any]:
        """Verify admin credentials and return a JWT token pair."""
        # W16-2: ADMIN_PASSWORD_SECRET takes priority (CI/CD / vault inject).
        # Falls back to legacy ADMIN_PASSWORD for backwards compat during migration.
        admin_password = (
            self.settings.admin_password_secret
            or self.settings.admin_password
            or "CHANGE_ME_IN_PROD"
        )
        if username != "admin" or password != admin_password:
            raise BizException(
                ErrorCode.AUTH_INVALID_CREDENTIALS, message="Invalid admin credentials"
            )

        token, exp = create_admin_token(admin_id=0, username=username)
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.login",
            payload={"username": username},
        )
        await self.db.commit()
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self.settings.access_token_ttl_minutes * 60,
        }

    # ------------------------------------------------------------------ #
    # User management                                                      #
    # ------------------------------------------------------------------ #
    async def list_users(
        self, page: int = 1, page_size: int = 20, status: Optional[str] = None
    ) -> dict[str, Any]:
        """Paginated user list, optionally filtered by status."""
        query = select(User).order_by(User.created_at.desc())
        if status:
            query = query.where(User.status == status)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        return {
            "items": [
                {
                    "id": r.id,
                    "uuid": r.uuid,
                    "phone": r.phone,
                    "phone_country": r.phone_country,
                    "nickname": r.nickname,
                    "language_pref": r.language_pref,
                    "status": r.status,
                    "created_at": r.created_at,
                }
                for r in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        }

    async def get_user(self, user_id: int) -> dict[str, Any]:
        """User detail or 404."""
        user = await self.db.get(User, user_id)
        if user is None:
            raise BizException(ErrorCode.USER_NOT_FOUND, message="User not found")
        return {
            "id": user.id,
            "uuid": user.uuid,
            "phone": user.phone,
            "phone_country": user.phone_country,
            "nickname": user.nickname,
            "language_pref": user.language_pref,
            "status": user.status,
            "created_at": user.created_at,
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

        return {
            "items": [
                {
                    "id": r.id,
                    "uuid": r.uuid,
                    "order_no": r.order_no,
                    "user_id": r.user_id,
                    "destination_id": r.destination_id,
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
        """Order detail or 404."""
        order = await self.db.get(Order, order_id)
        if order is None:
            raise BizException(ErrorCode.ORDER_NOT_FOUND, message="Order not found")
        return {
            "id": order.id,
            "uuid": order.uuid,
            "order_no": order.order_no,
            "user_id": order.user_id,
            "destination_id": order.destination_id,
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
            "applicant_data": order.applicant_data,
            "material_ids": order.material_ids,
        }

    async def update_order_status(
        self, order_id: int, new_status: str, note: Optional[str] = None
    ) -> dict[str, Any]:
        """Update order status (admin override)."""
        order = await self.db.get(Order, order_id)
        if order is None:
            raise BizException(ErrorCode.ORDER_NOT_FOUND, message="Order not found")
        if new_status not in ORDER_STATUSES:
            raise BizException(
                ErrorCode.ORDER_INVALID_STATE, message=f"Invalid status: {new_status}"
            )
        old_status = order.status
        order.status = new_status
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

    # ------------------------------------------------------------------ #
    # Country config                                                        #
    # ------------------------------------------------------------------ #
    async def list_countries(
        self, page: int = 1, page_size: int = 50, enabled: Optional[bool] = None
    ) -> dict[str, Any]:
        """Paginated country list."""
        query = select(VisaCountry).order_by(VisaCountry.country_code)
        if enabled is not None:
            query = query.where(VisaCountry.enabled == enabled)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        return {
            "items": [
                {
                    "id": r.id,
                    "country_code": r.country_code,
                    "country_name_zh": r.country_name_zh,
                    "country_name_en": r.country_name_en,
                    "enabled": r.enabled,
                    "base_url": r.base_url,
                    "form_path": r.form_path,
                    "rpa_config": r.rpa_config,
                    "visa_types": r.visa_types,
                    "fee_usd": r.fee_usd,
                    "processing_days": r.processing_days,
                    "extra": r.extra,
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

    async def create_country(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new country entry."""
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
            base_url=data.get("base_url"),
            form_path=data.get("form_path"),
            rpa_config=data.get("rpa_config"),
            visa_types=visa_types,
            fee_usd=data.get("fee_usd"),
            processing_days=data.get("processing_days"),
            extra=data.get("extra"),
        )
        self.db.add(country)
        await self.db.flush()
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.country.create",
            target_type="country",
            target_id=country.id,
        )
        await self.db.commit()
        return {
            "id": country.id,
            "country_code": country.country_code,
            "country_name_zh": country.country_name_zh,
            "country_name_en": country.country_name_en,
            "enabled": country.enabled,
        }

    async def update_country(self, country_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """Update country fields (partial update)."""
        country = await self.db.get(VisaCountry, country_id)
        if country is None:
            raise BizException(ErrorCode.NOT_FOUND, message="Country not found")

        if "country_name_zh" in data:
            country.country_name_zh = data["country_name_zh"]
        if "country_name_en" in data:
            country.country_name_en = data["country_name_en"]
        if "enabled" in data:
            country.enabled = data["enabled"]
        if "base_url" in data:
            country.base_url = data["base_url"]
        if "form_path" in data:
            country.form_path = data["form_path"]
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
        if "extra" in data:
            country.extra = data["extra"]

        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.country.update",
            target_type="country",
            target_id=country_id,
        )
        await self.db.commit()
        return {
            "id": country.id,
            "country_code": country.country_code,
            "enabled": country.enabled,
        }

    async def delete_country(self, country_id: int) -> None:
        """Soft-delete: set enabled=False (offline, not removed from DB)."""
        country = await self.db.get(VisaCountry, country_id)
        if country is None:
            raise BizException(ErrorCode.NOT_FOUND, message="Country not found")
        country.enabled = False
        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=0,
            action="admin.country.delete",
            target_type="country",
            target_id=country_id,
        )
        await self.db.commit()

    # ------------------------------------------------------------------ #
    # Validation rules                                                      #
    # ------------------------------------------------------------------ #
    async def get_validation_rules(self) -> list[dict[str, Any]]:
        """Return all rules as a list of dicts."""
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
                "params": json.loads(r.params) if r.params else {},
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

    def get_rpa_config(self) -> dict[str, Any]:
        """Load RPA config from YAML file."""
        path = self._rpa_config_path()
        if not path.exists():
            return {}
        try:
            import yaml

            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def update_rpa_config(self, updates: dict[str, Any]) -> dict[str, Any]:
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

        record_audit(
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
          - payment_success_rate: orders with submitted_at NOT NULL / total orders
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
        pending_statuses = ("created", "submitted")
        completed_statuses = ("approved", "closed")

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

        # payment_success_rate: orders with submitted_at not null / total
        q_total = select(func.count()).select_from(Order)
        total_orders = (await self.db.execute(q_total)).scalar() or 0
        q_paid = select(func.count()).select_from(Order).where(
            Order.submitted_at.isnot(None)
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
    async def list_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        action: Optional[str] = None,
        actor_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Paginated audit log list."""
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if action:
            query = query.where(AuditLog.action.like(f"{action}%"))
        if actor_type:
            query = query.where(AuditLog.actor_type == actor_type)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        return {
            "items": [
                {
                    "id": r.id,
                    "uuid": r.uuid,
                    "actor_type": r.actor_type,
                    "actor_id": r.actor_id,
                    "action": r.action,
                    "target_type": r.target_type,
                    "target_id": r.target_id,
                    "payload": r.payload,
                    "created_at": r.created_at,
                }
                for r in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        }
