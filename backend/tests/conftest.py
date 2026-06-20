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
@pytest_asyncio.fixture(loop_scope="session")
async def app():
    """Fresh FastAPI app instance per test.

    W21.3 fix: loop_scope="session" 避免 pytest-asyncio 默认每个 test 起新 event loop
    后, asyncpg engine 绑定旧 loop → "attached to a different loop" 报错.
    """
    # Force-import all ORM models so Base.metadata is fully populated
    # before drop_all / create_all runs. Without this, lazily-imported
    # models (e.g. SmsCode via /auth routes) are missing from
    # Base.metadata.tables on the first test that touches them, causing
    # "no such table: sms_codes" failures partway through the suite.
    import app.models  # noqa: F401  -- registers all ORM models
    from app.main import create_app
    from app.core.db import engine, Base

    # Create schema in a fresh in-memory engine per test would be cleaner,
    # but our settings are cached at import — so we drop + recreate tables.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    application = create_app()
    yield application
    # Don't dispose — next test will reuse the same engine. But we did
    # drop_all above so the state is fresh.


@pytest_asyncio.fixture(loop_scope="session")
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
