"""RAG auto-refresh (celery beat) — task logic and config gating.

Manual admin refresh (POST /api/v2/rag/refresh) is covered in
test_rag_pipeline.py; this file covers the periodic-task path added to
close the "更新签证的信息策略" gap (previously fully manual).
"""
from __future__ import annotations

import pytest

from app.core.db import AsyncSessionLocal
from app.models.rag import RagSource
from app.services.rag.refresh import CURATED_CONTENT
from app.tasks.rag_tasks import _refresh_all_sources, refresh_rag_sources_task


class TestRagAutoRefreshTask:
    async def test_refresh_all_sources_summarizes_ok_and_error(self, app):
        names = list(CURATED_CONTENT.keys())
        async with AsyncSessionLocal() as db:
            db.add(RagSource(name=names[0], country_code="GB", content_type="curated", enabled=True))
            # unknown curated name -> refresh_source returns status "error"
            db.add(RagSource(name="不存在的来源", country_code="ZZ", content_type="curated", enabled=True))
            await db.commit()

        summary = await _refresh_all_sources()
        assert summary["total"] == 2
        assert summary["refreshed"] == 1
        assert summary["errors"] == 1

    async def test_refresh_all_sources_no_sources_is_empty(self, app):
        summary = await _refresh_all_sources()
        assert summary == {"refreshed": 0, "errors": 0, "total": 0}

    def test_task_is_registered_under_expected_name(self):
        assert refresh_rag_sources_task.name == "app.tasks.rag_tasks.refresh_rag_sources_task"


class TestRagAutoRefreshBeatConfig:
    def test_beat_schedule_absent_when_disabled(self, monkeypatch):
        monkeypatch.setenv("RAG_AUTO_REFRESH_ENABLED", "0")
        from app.core.config import get_settings
        get_settings.cache_clear()
        try:
            import importlib
            import app.celery_app as celery_app_mod
            importlib.reload(celery_app_mod)
            assert not celery_app_mod.celery_app.conf.beat_schedule
        finally:
            get_settings.cache_clear()

    def test_beat_schedule_present_when_enabled(self, monkeypatch):
        monkeypatch.setenv("RAG_AUTO_REFRESH_ENABLED", "1")
        monkeypatch.setenv("RAG_AUTO_REFRESH_INTERVAL_HOURS", "12")
        from app.core.config import get_settings
        get_settings.cache_clear()
        try:
            import importlib
            import app.celery_app as celery_app_mod
            importlib.reload(celery_app_mod)
            schedule = celery_app_mod.celery_app.conf.beat_schedule
            assert "rag-refresh-visa-sources" in schedule
            entry = schedule["rag-refresh-visa-sources"]
            assert entry["task"] == "app.tasks.rag_tasks.refresh_rag_sources_task"
            assert entry["schedule"] == 12 * 3600.0
        finally:
            get_settings.cache_clear()
            monkeypatch.delenv("RAG_AUTO_REFRESH_ENABLED", raising=False)
            monkeypatch.delenv("RAG_AUTO_REFRESH_INTERVAL_HOURS", raising=False)
            importlib.reload(celery_app_mod)
