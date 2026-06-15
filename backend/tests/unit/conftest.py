"""Unit test conftest — adds tmp_db fixture on top of tests/conftest.py.

The tmp_db fixture creates a completely isolated sqlite temp file DB and
runs create_all on it, bypassing the app fixture (which imports paddleocr
and fails in .venv-test).  Tests using tmp_db are fully isolated from the
live visa_mvp.db.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


# --------------------------------------------------------------------------- #
# Session-scoped engine + factory (set up once per test session)               #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def _tmp_engine_and_factory():
    """Create an isolated tmpfile DB with all registered tables.

    This fixture runs at pytest session scope, BEFORE any tests execute,
    so there's no running event loop conflict.
    """
    import asyncio
    import tempfile
    import os

    from sqlalchemy.ext.asyncio import create_async_engine

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _init():
        from app.core.db import Base
        import app.models  # noqa: F401  -- register ORM models
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # At session scope there's no running loop yet
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_init())
    loop.close()

    yield {"engine": engine, "factory": factory, "db_path": db_path}

    # Teardown: close engine and remove temp file
    engine.sync_engine.dispose()
    os.unlink(db_path)


@pytest_asyncio.fixture
async def tmp_db(_tmp_engine_and_factory) -> AsyncSession:
    """Per-test session on the isolated temp DB, with tables cleared before each test."""
    from sqlalchemy import text

    engine = _tmp_engine_and_factory["engine"]
    factory = _tmp_engine_and_factory["factory"]

    # Drop all tables before each test for a clean slate
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'alembic_%'")
        )
        for row in result.fetchall():
            await conn.execute(text(f"DROP TABLE IF EXISTS {row[0]}"))

    # Recreate all tables (fresh empty DB for each test)
    from app.core.db import Base
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with factory() as session:
        yield session