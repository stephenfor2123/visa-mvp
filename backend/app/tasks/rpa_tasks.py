"""
Celery tasks for RPA visa application submission.

Tasks are dispatched by the /api/v2/rpa/submit endpoint and executed
by the Celery worker asynchronously.

Task flow:
    1. submit_visa_application_task  — main entry point, runs the full RPA flow
    2. check_rpa_status_task         — periodic polling of RPA provider status

Celery worker:
    cd backend && .venv/bin/celery -A app.celery_app worker --loglevel=INFO

Celery beat (for periodic tasks):
    cd backend && .venv/bin/celery -A app.celery_app beat --loglevel=INFO
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from celery import shared_task

# Legacy Indonesia/Vietnam providers remain on disk for reference but are NOT
# registered — those countries are customer markets, not visa destinations
# (docs/PRODUCT_SCOPE.md). Re-enable only if product scope expands.
from app.services.rpa.rpa_scheduler import RPAScheduler, TaskStatus

logger = logging.getLogger(__name__)

# Provider registry — country_code (upper) -> provider class
# Empty while FEATURE_RPA is off and no product-destination providers ship.
_PROVIDER_MAP: dict[str, type] = {}


def _get_scheduler() -> RPAScheduler:
    """Get the singleton RPAScheduler instance (same as the API router uses)."""
    # Import here to avoid circular imports
    from app.api.v2.rpa import get_scheduler as _get_scheduler_fn
    return _get_scheduler_fn()


def _run_async(coro) -> Any:
    """Run an async coroutine from a synchronous Celery task."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — create a new one (normal for worker main thread)
        return asyncio.run(coro)
    # Already inside an async context — use loop.run_in_executor won't help
    # because we're already in the worker thread. Create a new thread with its
    # own event loop.
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


# ────────────────────────────────────────────────────────────────────────────
# Task 1 — Submit visa application                                            #
# ────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, name="rpa.submit_visa_application")
def submit_visa_application_task(
    self,
    task_id: str,
    order_id: str,
    country_code: str,
    visa_type: str,
    passport_data: dict[str, Any],
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict[str, Any]:
    """
    Celery task: execute the full RPA submission for a visa application.

    Steps:
      1. Resolve the country-specific provider.
      2. Parse the application form.
      3. Solve CAPTCHA.
      4. Fill and submit the form.
      5. Update scheduler task state (DONE / FAILED).

    Parameters
    ----------
    task_id : str
        The RPA task ID created by RPAScheduler.submit_visa_application().
    order_id : str
        Order ID for record-keeping.
    country_code : str
        ISO 3166-1 alpha-2 code (e.g. ID, VN).
    visa_type : str
        Visa type within the country (e.g. visit_visa, e_visa).
    passport_data : dict
        Passport holder fields (surname, given_name, dob, passport_no, etc.).
    user_id : Optional[str]
        Owner user ID for logging.
    ip_address : Optional[str]
        Client IP for logging.

    Returns
    -------
    dict
        Result dict with keys: task_id, status, confirmation_no (or error_detail).
    """
    logger.info(
        "[Celery] submit_visa_application_task start: task_id=%s order_id=%s country=%s",
        task_id, order_id, country_code
    )

    scheduler = _get_scheduler()
    upper_cc = country_code.upper()

    try:
        # ── Resolve provider ──────────────────────────────────────────────
        provider_cls = _PROVIDER_MAP.get(upper_cc)
        if not provider_cls:
            raise ValueError(f"No RPA provider for country code: {country_code}")

        provider = provider_cls()

        # ── Step 1: Parse form ──────────────────────────────────────────────
        scheduler._update_task(task_id, TaskStatus.WAITING, progress=0.2, message="Loading application form...")
        form_html = _run_async(provider.fetch_form())
        parsed = provider.parse_form(form_html)
        logger.debug("[%s] Form parsed: %d fields", task_id, len(parsed))

        # ── Step 2: Solve CAPTCHA ─────────────────────────────────────────
        scheduler._update_task(task_id, TaskStatus.WAITING, progress=0.4, message="Solving CAPTCHA...")
        captcha_info = provider.extract_captcha(form_html)
        captcha_solution = ""
        if captcha_info and captcha_info.image_data:
            captcha_solution = _run_async(provider.solve_captcha(captcha_info))

        # ── Step 3: Fill & submit form ─────────────────────────────────────
        scheduler._update_task(task_id, TaskStatus.WAITING, progress=0.6, message="Filling application form...")
        result = _run_async(
            provider.submit_application(
                parsed,
                passport_data,
                visa_type=visa_type,
                captcha_solution=captcha_solution,
            )
        )

        # ── Step 4: Update scheduler on success ────────────────────────────
        confirmation_no = result.get("confirmation_no", task_id)
        scheduler.mark_done(
            task_id,
            confirmation_no=confirmation_no,
            message="Application submitted successfully",
        )
        logger.info(
            "[Celery] submit_visa_application_task DONE: task_id=%s confirmation=%s",
            task_id, confirmation_no
        )
        return {
            "task_id": task_id,
            "status": "done",
            "confirmation_no": confirmation_no,
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("[Celery] submit_visa_application_task FAILED: task_id=%s", task_id)
        scheduler.mark_failed(
            task_id,
            error_detail=str(exc),
            message="Submission failed",
        )
        # Re-raise so Celery marks the task as FAILURE (not SUCCESS with result)
        raise


# ────────────────────────────────────────────────────────────────────────────
# Task 2 — Periodic status check (for WAITING tasks that may auto-complete)   #
# ────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, name="rpa.check_rpa_status")
def check_rpa_status_task(
    self,
    task_id: str,
    order_id: str,
    country_code: str,
    visa_type: str,
    passport_data: dict[str, Any],
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict[str, Any]:
    """
    Celery task: check the status of an in-progress (WAITING) RPA submission.

    This task is dispatched by a polling loop or by the Celery beat schedule.
    For providers that require asynchronous confirmation numbers (e.g. polling
    a reference page after submission), this task fetches the status page and
    updates the scheduler.

    Parameters
    ----------
    task_id : str
        The RPA task ID created by RPAScheduler.submit_visa_application().
    order_id : str
        Order ID for record-keeping.
    country_code : str
        ISO 3166-1 alpha-2 code (e.g. ID, VN).
    visa_type : str
        Visa type within the country.
    passport_data : dict
        Passport holder fields.
    user_id : Optional[str]
        Owner user ID for logging.
    ip_address : Optional[str]
        Client IP for logging.

    Returns
    -------
    dict
        Updated status dict.
    """
    logger.info(
        "[Celery] check_rpa_status_task: task_id=%s order_id=%s country=%s",
        task_id, order_id, country_code
    )

    scheduler = _get_scheduler()
    upper_cc = country_code.upper()

    # Guard: only check WAITING tasks
    status_info = scheduler.get_task_status(task_id)
    if status_info.get("status") not in ("waiting", "submitting"):
        logger.debug("[%s] Skipping status check — task not WAITING (status=%s)",
                     task_id, status_info.get("status"))
        return status_info

    try:
        provider_cls = _PROVIDER_MAP.get(upper_cc)
        if not provider_cls:
            raise ValueError(f"No RPA provider for country code: {country_code}")

        provider = provider_cls()
        result = _run_async(provider.check_application_status(task_id, order_id))

        if result.get("status") == "done":
            scheduler.mark_done(
                task_id,
                confirmation_no=result.get("confirmation_no", task_id),
                message=result.get("message", "Status check: confirmed"),
            )
        elif result.get("status") == "failed":
            scheduler.mark_failed(
                task_id,
                error_detail=result.get("error_detail", "Status check failed"),
                message=result.get("message", "Status check: failed"),
            )
        else:
            # Still in progress — update progress and re-queue
            scheduler._update_task(
                task_id,
                TaskStatus.WAITING,
                progress=min(0.9, status_info.get("progress", 0.5) + 0.1),
                message=result.get("message", "Status check: still processing"),
            )
            # Re-queue for another check in 30 s
            check_rpa_status_task.apply_async(
                args=[task_id, order_id, country_code, visa_type, passport_data, user_id, ip_address],
                countdown=30,
            )

        return scheduler.get_task_status(task_id)

    except Exception as exc:  # noqa: BLE001
        logger.exception("[Celery] check_rpa_status_task FAILED: task_id=%s", task_id)
        # Don't mark failed on check error — let the task stay WAITING for next beat
        return {
            "task_id": task_id,
            "status": "error",
            "message": f"Status check error: {exc}",
        }