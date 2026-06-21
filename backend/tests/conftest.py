"""Pytest config — every test gets a fresh, in-process FastAPI app
backed by a throwaway SQLite file in a temp dir."""
from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ----------------------------------------------------------------- #
# Test environment — must be set BEFORE app.config is imported       #
# ----------------------------------------------------------------- #
@pytest.fixture(scope="session", autouse=True)
def _test_env() -> Generator[None, None, None]:
    """Pin a per-session test env: temp DB, no rate limiting noise."""
    tmpdir = tempfile.mkdtemp(prefix="visa-mvp-test-")
    db_path = Path(tmpdir) / "test.db"
    log_dir = Path(tmpdir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["LOG_DIR"] = str(log_dir)
    os.environ["SMS_LOG_DIR"] = str(log_dir)
    os.environ["SMS_COOLDOWN_SECONDS"] = "1"        # test-friendly cooldown
    os.environ["SMS_DAILY_LIMIT"] = "10000"          # disable for tests
    os.environ["RATE_LIMIT_PER_IP_PER_MIN"] = "10000"  # disable IP rate limit
    os.environ["RATE_LIMIT_SLOW_API_PER_IP_PER_MIN"] = "10000"
    os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-2026"
    os.environ["ADMIN_PASSWORD_SECRET"] = "visa-admin-2024"
    os.environ["ENV"] = "test"
    os.environ["DB_ECHO"] = "0"

    # Reset cached settings + global state
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    # Reset rate limiter singleton between modules
    from app.middleware.rate_limit import InMemoryRateLimiter
    InMemoryRateLimiter()

    yield
    # Teardown
    try:
        db_path.unlink(missing_ok=True)
    except Exception:
        pass


# ----------------------------------------------------------------- #
# App + DB + client fixtures                                          #
# ----------------------------------------------------------------- #
@pytest_asyncio.fixture()
async def app():
    """Fresh FastAPI app instance per test, with a per-test async engine.

    Root cause (W22): app.core.db module-level `engine` and AsyncSessionLocal
    are created at import time (first test's event loop).  Subsequent tests
    run in a new pytest-asyncio event loop but reuse the same engine → 
    "Future attached to a different loop" / "another operation is in progress".

    Fix: inside this fixture (which runs inside pytest-asyncio's per-test loop)
    we create a fresh test engine and patch app.core.db module-level objects
    so that lifespan() and get_db() both use the correct, loop-bound engine.
    """
    import app.models  # noqa: F401  -- registers all ORM models
    from app.main import create_app
    from app.core import db as db_module
    from app.core.db import Base
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = os.environ["DATABASE_URL"]
    is_sqlite = "sqlite" in db_url

    # Create a fresh engine bound to THIS fixture's event loop (the current loop).
    test_engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )
    TestSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
        autoflush=False,
    )

    # Replace module-level objects so lifespan() + get_db() pick up the test engine.
    old_engine = db_module.engine
    old_session_local = db_module.AsyncSessionLocal

    db_module.engine = test_engine
    db_module.AsyncSessionLocal = TestSessionLocal

    # Also patch get_db to use our TestSessionLocal (reads AsyncSessionLocal at call time).
    async def _test_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    db_module.get_db = _test_get_db

    # Create schema using the fresh test engine.
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    application = create_app()
    yield application

    # Cleanup: restore originals, dispose test engine.
    db_module.engine = old_engine
    db_module.AsyncSessionLocal = old_session_local
    db_module.get_db = old_session_local  # restore using old_session_local as callable

    await test_engine.dispose()


@pytest_asyncio.fixture()
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the in-process ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ----------------------------------------------------------------- #
# Convenience helpers                                                #
# ----------------------------------------------------------------- #
@pytest.fixture()
def default_phone() -> str:
    return "13800138000"


@pytest.fixture()
def default_password() -> str:
    return "abc12345"


@pytest.fixture()
def default_sms_code() -> str:
    return "123456"
