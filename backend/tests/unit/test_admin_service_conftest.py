"""conftest for admin_service tests — isolated tmpfile SQLite DB.

Avoids touching the live visa_mvp.db.  Overrides get_db so AdminService
uses the temp DB for all its queries.
"""
from __future__ import annotations

import asyncio
import tempfile
import os
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


# --------------------------------------------------------------------------- #
# Session-scoped tmpfile DB                                                   #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def _tmp_db_url() -> str:
    """Create a temp SQLite file for the entire test session."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = tmp.name
    tmp.close()
    return f"sqlite+aiosqlite:///{path}"


@pytest.fixture(scope="session")
def _tmp_engine(_tmp_db_url: str):
    """Create an async engine on the tmpfile DB and create all required tables."""
    engine = create_async_engine(_tmp_db_url, echo=False)

    async def _init():
        async with engine.begin() as conn:
            # Users
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS users ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  uuid TEXT UNIQUE,"
                "  phone TEXT,"
                "  phone_country TEXT,"
                "  nickname TEXT,"
                "  language_pref TEXT DEFAULT 'zh-CN',"
                "  status TEXT DEFAULT 'active',"
                "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            ))
            # Orders
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS orders ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  uuid TEXT UNIQUE,"
                "  order_no TEXT UNIQUE,"
                "  user_id INTEGER,"
                "  destination_id INTEGER,"
                "  visa_type TEXT,"
                "  status TEXT DEFAULT 'submitted',"
                "  total_amount REAL DEFAULT 0.0,"
                "  currency TEXT DEFAULT 'USD',"
                "  rpa_task_id TEXT,"
                "  aff_code TEXT,"
                "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
                "  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            ))
            # Visa countries
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS visa_countries ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  country_code TEXT UNIQUE,"
                "  country_name_zh TEXT,"
                "  country_name_en TEXT,"
                "  enabled INTEGER DEFAULT 1,"
                "  base_url TEXT,"
                "  form_path TEXT,"
                "  rpa_config TEXT,"
                "  visa_types TEXT,"
                "  fee_usd TEXT,"
                "  processing_days INTEGER,"
                "  extra TEXT,"
                "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
                "  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            ))
            # Audit logs
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS audit_log ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  actor_type TEXT,"
                "  actor_id TEXT,"
                "  action TEXT,"
                "  resource_type TEXT,"
                "  resource_id TEXT,"
                "  detail TEXT,"
                "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            ))

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_init())
    loop.close()
    yield engine
    engine.sync_engine.dispose()
    os.unlink(_tmp_db_url.replace("sqlite+aiosqlite:///", ""))


@pytest.fixture(scope="session")
def _tmp_session_factory(_tmp_engine):
    return async_sessionmaker(
        _tmp_engine, expire_on_commit=False, class_=AsyncSession
    )


@pytest.fixture
async def tmp_db(_tmp_session_factory) -> AsyncSession:
    """Per-test session on the isolated DB, always empty (no shared state)."""
    async with _tmp_session_factory() as session:
        yield session