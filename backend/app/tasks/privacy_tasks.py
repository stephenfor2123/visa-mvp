"""Celery tasks for GDPR retention + 72h account destroy."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _run_destroy() -> dict[str, Any]:
    from app.core.db import AsyncSessionLocal
    from app.services.cleanup_service import CleanupService

    async with AsyncSessionLocal() as db:
        return await CleanupService(db).run_pending_destroy_users(actor_type="system")


async def _run_retention() -> dict[str, Any]:
    from app.core.db import AsyncSessionLocal
    from app.services.cleanup_service import CleanupService

    async with AsyncSessionLocal() as db:
        return await CleanupService(db).run_retention_purge(actor_type="system")


@celery_app.task(name="app.tasks.privacy_tasks.run_pending_destroy_users_task")
def run_pending_destroy_users_task() -> dict[str, Any]:
    """Daily: purge users in pending_destroy past the 72h grace window."""
    result = _run_async(_run_destroy())
    logger.info("privacy.destroy_job done: %s", result)
    return result


@celery_app.task(name="app.tasks.privacy_tasks.run_retention_purge_task")
def run_retention_purge_task() -> dict[str, Any]:
    """Daily: materials 90d / applicant_data 180d after retention_anchor_at."""
    result = _run_async(_run_retention())
    logger.info("privacy.retention_purge done: %s", result)
    return result
