"""
RPA Scheduler — Task state machine, rate limiting, and submission orchestration.

Task lifecycle:
  IDLE → SUBMITTING → WAITING → DONE / FAILED

Usage:
    scheduler = RPAScheduler()
    task_id = scheduler.submit_visa_application(order_id)
    status = scheduler.get_task_status(task_id)
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import yaml

from app.core.config import BACKEND_ROOT

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """RPA task lifecycle states."""
    IDLE = "idle"
    SUBMITTING = "submitting"
    WAITING = "waiting"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RPATask:
    """Represents a single RPA submission task."""
    task_id: str
    order_id: str
    country_code: str
    visa_type: str
    status: TaskStatus
    progress: float = 0.0  # 0.0–1.0
    message: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    confirmation_no: Optional[str] = None
    error_detail: Optional[str] = None
    attempts: int = 0
    user_id: Optional[str] = None  # Owner user ID for ownership verification


class RateLimitExceeded(Exception):
    """Raised when a rate limit is hit."""
    pass


class RPASchedulerError(Exception):
    """Raised when RPA scheduling fails."""
    pass


class RPAScheduler:
    """
    Orchestrate visa application submissions via RPA.

    Manages:
      - Task state machine (IDLE → SUBMITTING → WAITING → DONE/FAILED)
      - Per-IP daily visit limits
      - Per-account submission interval limits
      - Concurrent task limits per account

    Parameters
    ----------
    config_path : Optional[str]
        Path to rpa_config.yaml.
    """

    # Valid state transitions
    _VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
        TaskStatus.IDLE: {TaskStatus.SUBMITTING},
        TaskStatus.SUBMITTING: {TaskStatus.WAITING, TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.WAITING: {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.DONE: set(),
        TaskStatus.FAILED: set(),
        TaskStatus.CANCELLED: set(),
    }

    def __init__(self, config_path: Optional[str] = None) -> None:
        self._config_path = config_path or str(BACKEND_ROOT / "data" / "rpa_config.yaml")
        self._load_config()

        # In-memory task store (production: Redis + DB)
        self._tasks: dict[str, RPATask] = {}
        # W22 fix: lazy lock init — 创建 asyncio.Lock 在 Python 3.10+ 绑当前 event loop
        # 在 asyncio.run() 后, 已关闭 loop 上的 lock 不能跨 thread 复用.
        # 改成懒加载: 第一次用时建新 lock
        self._lock: Optional[asyncio.Lock] = None

        # Rate limit tracking: IP -> list of timestamps
        self._ip_visits: dict[str, list[datetime]] = {}
        # Account -> last submission time
        self._account_last_submit: dict[str, datetime] = {}
        # Account -> active task count
        self._account_active_tasks: dict[str, int] = {}

    def _load_config(self) -> None:
        """Load RPA config from YAML."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning("rpa_config.yaml not found, using defaults")
            self._config = {}
        except yaml.YAMLError as exc:
            logger.error("Failed to parse rpa_config.yaml: %s", exc)
            self._config = {}

    @property
    def mock_mode(self) -> bool:
        """Whether mock mode is enabled."""
        return self._config.get("mock_mode", True)

    def get_config(self) -> dict[str, Any]:
        """Return current RPA configuration (safe subset, no secrets)."""
        rl = self._config.get("rate_limits", {})
        to = self._config.get("timeouts", {})
        retry = self._config.get("retry", {})
        return {
            "rate_limits": {
                "ip_per_day": rl.get("ip_per_day", 50),
                "account_interval_minutes": rl.get("account_interval_minutes", 30),
                "max_concurrent_tasks": rl.get("max_concurrent_tasks", 2),
            },
            "timeouts": {
                "http_timeout": to.get("http_timeout", 30),
                "captcha_timeout": to.get("captcha_timeout", 20),
                "submit_timeout": to.get("submit_timeout", 60),
            },
            "retry": {
                "captcha_max_retries": retry.get("captcha_max_retries", 3),
                "page_max_retries": retry.get("page_max_retries", 2),
            },
            "countries": {
                k: v.get("enabled", False)
                for k, v in self._config.get("countries", {}).items()
            },
            "mock_mode": self.mock_mode,
        }

    def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """
        Update RPA configuration (runtime, not persisted to file).

        Parameters
        ----------
        updates : dict
            Partial config dict. Top-level keys (`rate_limits`, `timeouts`,
            `retry`, `mock_mode`, `countries`) are upserted; nested dicts are
            merged in place.

        Returns
        -------
        dict
            Updated config snapshot.
        """
        for key, value in updates.items():
            if key in ("rate_limits", "timeouts", "retry", "mock_mode", "countries"):
                if key in self._config and isinstance(self._config[key], dict) and isinstance(value, dict):
                    self._config[key].update(value)
                else:
                    self._config[key] = value
        return self.get_config()

    def submit_visa_application(
        self,
        order_id: str,
        country_code: str,
        visa_type: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """
        Create and start a new RPA submission task.

        Parameters
        ----------
        order_id : str
            The order ID to submit.
        country_code : str
            ISO 3166-1 alpha-2 country code.
        visa_type : str
            Visa type within the country.
        user_id : Optional[str]
            User account ID (for rate limiting).
        ip_addre : Optional[str] = None
            Client IP address (for IP rate limiting).

        Returns
        -------
        str
            The task_id for this submission.

        Raises
        ------
        RateLimitExceeded
            If IP daily limit or account interval limit is exceeded.
        RPASchedulerError
            If concurrent task limit is exceeded or country is disabled.
        """
        user_id = user_id or "anonymous"
        ip_address = ip_address or "0.0.0.0"

        # Check IP daily limit
        self._check_ip_rate_limit(ip_address)

        # Check account submission interval
        self._check_account_interval(user_id)

        # Check concurrent task limit
        self._check_concurrent_limit(user_id)

        # Check country enabled (case-insensitive lookup, supports both ISO codes and names)
        countries = self._config.get("countries", {})
        # ISO code → config key mapping
        ISO_TO_NAME = {
            "ID": "Indonesia", "VN": "Vietnam", "PH": "Philippines",
            "TH": "Thailand", "MY": "Malaysia", "SG": "Singapore",
            "CN": "China", "JP": "Japan", "KR": "Korea",
        }
        resolved_code = ISO_TO_NAME.get(country_code, country_code)
        country_config = (
            countries.get(resolved_code)
            or countries.get(country_code)
            or countries.get(country_code.lower())
            or countries.get(country_code.title())
            or {}
        )
        if not country_config.get("enabled", False):
            raise RPASchedulerError(f"Country {country_code} is not enabled for RPA")

        # Create task
        task_id = f"rpa-{uuid.uuid4().hex[:11]}"  # "rpa-" (4) + 11 hex chars = 15
        task = RPATask(
            task_id=task_id,
            order_id=order_id,
            country_code=country_code.upper(),
            visa_type=visa_type,
            status=TaskStatus.SUBMITTING,
            progress=0.0,
            message="Task created, initiating submission",
            user_id=user_id,
        )

        self._tasks[task_id] = task
        self._ip_visits.setdefault(ip_address, []).append(datetime.utcnow())
        self._account_active_tasks[user_id] = self._account_active_tasks.get(user_id, 0) + 1
        # Record the submission time so the per-account interval check fires
        # on the next submit_visa_application() call.
        self._account_last_submit[user_id] = datetime.utcnow()

        logger.info(
            "RPA task created: task_id=%s order_id=%s country=%s visa_type=%s user=%s ip=%s",
            task_id, order_id, country_code, visa_type, user_id, ip_address
        )

        # In production: dispatch to Celery worker here
        # For MVP: just record the task (worker logic lives in providers)
        self._update_task(task_id, TaskStatus.SUBMITTING, progress=0.1, message="Submitting form")

        return task_id

    def get_task_status(
        self, task_id: str, owner_user_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Get the current status of an RPA task.

        Parameters
        ----------
        task_id : str
            The task ID returned by submit_visa_application().
        owner_user_id : Optional[str]
            If provided, verifies the task belongs to this user and raises
            RPASchedulerError if not. Prevents IDOR on task status queries.

        Returns
        -------
        dict
            Status dict with keys: task_id, status, progress (0.0–1.0),
            message, confirmation_no, error_detail, timestamps.
        """
        task = self._tasks.get(task_id)
        if not task:
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": f"Task {task_id} not found",
            }

        if owner_user_id is not None and task.user_id != owner_user_id:
            # Silently return not_found to avoid leaking existence
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": f"Task {task_id} not found",
            }

        return {
            "task_id": task.task_id,
            "order_id": task.order_id,
            "country_code": task.country_code,
            "visa_type": task.visa_type,
            "status": task.status.value,
            "progress": task.progress,
            "message": task.message,
            "confirmation_no": task.confirmation_no,
            "error_detail": task.error_detail,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "attempts": task.attempts,
        }

    def cancel_task(
        self, task_id: str, owner_user_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Cancel a pending or in-progress RPA task.

        Parameters
        ----------
        task_id : str
            The task ID to cancel.
        owner_user_id : Optional[str]
            If provided, verifies the task belongs to this user before cancelling.

        Returns
        -------
        dict
            Updated status dict.
        """
        task = self._tasks.get(task_id)
        if not task:
            return {"task_id": task_id, "status": "not_found"}

        if owner_user_id is not None and task.user_id != owner_user_id:
            return {"task_id": task_id, "status": "not_found"}

        if task.status not in (TaskStatus.IDLE, TaskStatus.SUBMITTING, TaskStatus.WAITING):
            # W22 fix: include progress field so RPATaskStatus response validation passes
            return {
                "task_id": task_id,
                "status": task.status.value,
                "progress": task.progress,
                "message": f"Cannot cancel task in status '{task.status.value}'",
            }

        self._update_task(
            task_id,
            TaskStatus.CANCELLED,
            progress=task.progress,
            message="Cancelled by user",
        )
        return self.get_task_status(task_id)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    def _check_ip_rate_limit(self, ip_address: str) -> None:
        """Check and enforce IP per-day visit limit."""
        rl = self._config.get("rate_limits", {})
        max_per_day = rl.get("ip_per_day", 50)

        visits = self._ip_visits.get(ip_address, [])
        # Filter to today's visits only
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        recent_visits = [v for v in visits if v >= today]

        if len(recent_visits) >= max_per_day:
            raise RateLimitExceeded(
                f"IP {ip_address} has reached the daily limit of {max_per_day} visits. "
                f"Try again tomorrow."
            )

    def _check_account_interval(self, user_id: str) -> None:
        """Check and enforce minimum interval between submissions per account."""
        rl = self._config.get("rate_limits", {})
        interval_min = rl.get("account_interval_minutes", 30)

        last_submit = self._account_last_submit.get(user_id)
        if last_submit:
            elapsed = datetime.utcnow() - last_submit
            if elapsed < timedelta(minutes=interval_min):
                remaining = interval_min * 60 - elapsed.total_seconds()
                raise RateLimitExceeded(
                    f"Account {user_id} must wait {int(remaining)}s before submitting again "
                    f"(minimum interval: {interval_min} minutes)."
                )

    def _check_concurrent_limit(self, user_id: str) -> None:
        """Check and enforce max concurrent tasks per account."""
        rl = self._config.get("rate_limits", {})
        max_concurrent = rl.get("max_concurrent_tasks", 2)

        active = self._account_active_tasks.get(user_id, 0)
        if active >= max_concurrent:
            raise RPASchedulerError(
                f"Account {user_id} has {active} active tasks (max: {max_concurrent}). "
                f"Wait for a task to complete before submitting a new one."
            )

    def _update_task(
        self,
        task_id: str,
        status: TaskStatus,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        confirmation_no: Optional[str] = None,
        error_detail: Optional[str] = None,
    ) -> None:
        """Update task state and metadata."""
        task = self._tasks.get(task_id)
        if not task:
            return

        # Validate state transition
        valid_next = self._VALID_TRANSITIONS.get(task.status, set())
        if status not in valid_next:
            logger.warning(
                "Invalid state transition: %s -> %s (valid: %s)",
                task.status.value, status.value, valid_next
            )
            # Allow same-state updates (heartbeat, progress bump)
            if task.status == status:
                pass
            else:
                return

        task.status = status
        task.updated_at = datetime.utcnow()

        if progress is not None:
            task.progress = max(0.0, min(1.0, progress))
        if message is not None:
            task.message = message
        if confirmation_no is not None:
            task.confirmation_no = confirmation_no
        if error_detail is not None:
            task.error_detail = error_detail

        if status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = datetime.utcnow()
            # Decrement active task counter
            for uid in self._account_active_tasks:
                if self._account_active_tasks[uid] > 0:
                    self._account_active_tasks[uid] -= 1
            # Record last submit time
            self._account_last_submit[uid] = datetime.utcnow()

        logger.debug(
            "Task %s updated: status=%s progress=%.2f msg='%s'",
            task_id, status.value, task.progress, task.message
        )

    def mark_done(
        self,
        task_id: str,
        confirmation_no: str,
        message: str = "Application submitted successfully",
    ) -> None:
        """Mark a task as successfully completed."""
        self._update_task(
            task_id,
            TaskStatus.DONE,
            progress=1.0,
            message=message,
            confirmation_no=confirmation_no,
        )

    def mark_failed(
        self,
        task_id: str,
        error_detail: str,
        message: str = "Submission failed",
    ) -> None:
        """Mark a task as failed."""
        self._update_task(
            task_id,
            TaskStatus.FAILED,
            message=message,
            error_detail=error_detail,
        )

    def list_tasks(
        self,
        order_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> list[dict[str, Any]]:
        """List tasks matching the given filters."""
        results = []
        for task in self._tasks.values():
            if order_id and task.order_id != order_id:
                continue
            if status and task.status != status:
                continue
            results.append(self.get_task_status(task.task_id))
        return results


# --------------------------------------------------------------------------- #
# Singleton management — exposed for both API and test imports                 #
# --------------------------------------------------------------------------- #
_scheduler: Optional[RPAScheduler] = None


def get_scheduler() -> RPAScheduler:
    """Get or create the singleton RPAScheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = RPAScheduler()
    return _scheduler


# --------------------------------------------------------------------------- #
# Test helper — reset the singleton between tests                              #
# --------------------------------------------------------------------------- #
def reset_scheduler_for_tests() -> None:
    """Clear all in-memory task state so tests start with a clean slate."""
    global _scheduler
    if _scheduler is not None:
        _scheduler._tasks.clear()
        _scheduler._ip_visits.clear()
        _scheduler._account_last_submit.clear()
        _scheduler._account_active_tasks.clear()
    _scheduler = None