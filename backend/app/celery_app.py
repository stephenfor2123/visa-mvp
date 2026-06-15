"""
Celery application instance — Redis-backed broker + result backend.

Import this module FIRST (before any task modules) to register the app:
    from app.celery_app import celery_app

Run worker:
    cd backend && .venv/bin/celery -A app.celery_app worker --loglevel=INFO

Run beat (for periodic tasks):
    cd backend && .venv/bin/celery -A app.celery_app beat --loglevel=INFO
"""
from __future__ import annotations

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "visa_mvp",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.rpa_tasks"],
)

# ── Serialiser (JSON so it works across processes) ──────────────────────────
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    # Task result expiry (24 h)
    result_expires=86400,
    # Task track_started so PENDING → STARTED is visible
    task_track_started=True,
    # Don't re-queue failed tasks automatically (let them surface as FAILED)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Redis result backend config
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 43200,
    },
)

# ── Discover tasks from all registered packages ─────────────────────────────
# (done automatically by `include=[]` above)