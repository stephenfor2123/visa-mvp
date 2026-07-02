"""Celery task: periodic RAG source refresh (auto-update visa policy info).

Wired into celery beat via `app.celery_app` when
`RAG_AUTO_REFRESH_ENABLED=1` (see app/core/config.py). Off by default —
refresh hits real government websites, so it's opt-in per environment.

Manual trigger stays available regardless of this setting via the admin
endpoint `POST /api/v2/rag/refresh`.

Celery worker:
    cd backend && .venv/bin/celery -A app.celery_app worker --loglevel=INFO
Celery beat:
    cd backend && .venv/bin/celery -A app.celery_app beat --loglevel=INFO
"""
from __future__ import annotations

import asyncio
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a synchronous Celery task (same bridge
    pattern as app.tasks.rpa_tasks._run_async)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


async def _refresh_all_sources() -> dict:
    from app.core.db import AsyncSessionLocal
    from app.services.rag.refresh import refresh_all

    async with AsyncSessionLocal() as db:
        results = await refresh_all(db)
        refreshed = sum(1 for r in results if r.get("status") == "ok")
        errors = sum(1 for r in results if r.get("status") == "error")
        return {"refreshed": refreshed, "errors": errors, "total": len(results)}


@shared_task(name="app.tasks.rag_tasks.refresh_rag_sources_task")
def refresh_rag_sources_task() -> dict:
    """Re-fetch + re-embed every enabled RAG source (visa policy pages)."""
    summary = _run_async(_refresh_all_sources())
    if summary["errors"]:
        logger.warning("RAG auto-refresh completed with errors: %s", summary)
    else:
        logger.info("RAG auto-refresh completed: %s", summary)
    return summary
