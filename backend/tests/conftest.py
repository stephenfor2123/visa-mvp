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
    os.environ["EMAIL_COOLDOWN_SECONDS"] = "1"
    os.environ["EMAIL_DAILY_LIMIT"] = "10000"
    os.environ["RATE_LIMIT_PER_IP_PER_MIN"] = "10000"  # disable IP rate limit
    os.environ["RATE_LIMIT_SLOW_API_PER_MIN"] = "10000"
    os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-2026"
    os.environ["ADMIN_PASSWORD_SECRET"] = "visa-admin-2024"
    os.environ["ENV"] = "test"
    os.environ["DB_ECHO"] = "0"
    os.environ["MATERIAL_STORAGE_ENABLED"] = "1"
    os.environ["PAYMENT_CHANNEL"] = "mock"
    os.environ["STRIPE_SECRET_KEY"] = ""
    os.environ["STRIPE_PUBLISHABLE_KEY"] = ""
    os.environ["STRIPE_WEBHOOK_SECRET"] = ""
    os.environ["RESEND_API_KEY"] = ""

    # Reset cached settings + global state
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    # Reset rate limiter singleton between modules
    from app.middleware.rate_limit import InMemoryRateLimiter
    InMemoryRateLimiter()
    # Reset DS-160 in-memory rate limiter too (P1: swap to Redis)
    try:
        from app.core.ds160 import get_default_rate_limiter
        get_default_rate_limiter().reset()
    except Exception:
        pass

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

    CRITICAL additional fix: aiosqlite uses a SEPARATE connection per session.
    When two async sessions (one from _seed_destination, one from the API's
    get_db) open separate connections to the same in-memory DB, the second
    connection starts EMPTY (SQLite in-memory is connection-local).
    Solution: (a) use a named in-memory URI with a shared cache so all
    connections share the same data, AND (b) patch AsyncSessionLocal.kw['bind']
    to point to the test engine so that code which already imported
    AsyncSessionLocal (e.g. test_orders.py, test_checklist.py) automatically
    uses the test engine.
    """
    import app.models  # noqa: F401  -- registers all ORM models
    from app.main import create_app
    from app.core import db as db_module
    from app.core.db import Base
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    # Always use a fresh shared-cache in-memory SQLite per test, regardless
    # of what DATABASE_URL is set to in .env (CI overrides it to Postgres).
    import uuid
    _mem_name = f"file:visa_test_{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true"
    db_url = f"sqlite+aiosqlite:///{_mem_name}"

    # Create a fresh engine bound to THIS fixture's event loop.
    test_engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )
    TestSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
        autoflush=False,
    )

    # Save originals for cleanup
    old_engine = db_module.engine
    old_session_local = db_module.AsyncSessionLocal
    old_get_db = db_module.get_db

    # Patch engine in app.main — it does `from app.core.db import engine` and
    # uses the bound name inside lifespan().
    import app.main as main_module
    old_main_engine = main_module.engine
    main_module.engine = test_engine
    db_module.engine = test_engine

    # CRITICAL: patch AsyncSessionLocal.kw['bind'] so that code which already
    # imported AsyncSessionLocal (test_orders.py, test_checklist.py, and the
    # original get_db) automatically uses the test engine.  This works because
    # async_sessionmaker.__call__ reads kw['bind'] to determine the session's
    # bind at call time.
    # Also patch autoflush to False to match TestSessionLocal.
    old_bind = db_module.AsyncSessionLocal.kw.get("bind")
    db_module.AsyncSessionLocal.kw["bind"] = test_engine
    db_module.AsyncSessionLocal.kw["autoflush"] = False
    db_module.AsyncSessionLocal.kw["expire_on_commit"] = False

    # Override get_db to use the test sessionmaker directly.
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

    # Also patch router modules that have their own get_db bindings
    # (FastAPI captured the original get_db at decoration time).
    _original_router_attrs: dict[tuple[str, str], object] = {}

    def _safe_patch(module_name: str, attr: str, new_value) -> None:
        try:
            mod = __import__(module_name, fromlist=[attr])
            if hasattr(mod, attr):
                _original_router_attrs[(module_name, attr)] = getattr(mod, attr)
                setattr(mod, attr, new_value)
        except Exception:
            pass

    for module_name, attr in [
        ("app.api.v2.orders", "get_db"),
        ("app.api.v2.auth", "get_db"),
        ("app.api.v2.payment", "get_db"),
        ("app.api.v2.materials", "get_db"),
        ("app.api.v2.admin", "get_db"),
        ("app.api.v2.destinations", "get_db"),
        ("app.api.v2.ocr", "get_db"),
        ("app.api.v2.rpa", "get_db"),
        ("app.api.v2.voice", "get_db"),
        ("app.api.v2.scheduler", "get_db"),
        ("app.api.v2.affiliate", "get_db"),
        ("app.api.v2.analytics", "get_db"),
        ("app.api.v2.ds160", "get_db"),
        ("app.core.security", "get_db"),
    ]:
        _safe_patch(module_name, attr, _test_get_db)

    # Create schema using the fresh test engine.
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    application = create_app()
    yield application

    # Cleanup: restore originals, dispose test engine
    db_module.engine = old_engine
    db_module.AsyncSessionLocal.kw["bind"] = old_bind
    db_module.AsyncSessionLocal.kw["autoflush"] = True
    db_module.AsyncSessionLocal.kw["expire_on_commit"] = False
    db_module.get_db = old_get_db
    main_module.engine = old_main_engine
    # Restore router module bindings
    for (module_name, attr), original_value in _original_router_attrs.items():
        try:
            mod = __import__(module_name, fromlist=[attr])
            setattr(mod, attr, original_value)
        except Exception:
            pass

    await test_engine.dispose()


@pytest.fixture(autouse=True)
def _bypass_sensitive_consent(request):
    """Neutralize the GDPR sensitive-processing consent gate for flow tests.

    The consent gate (materials upload / OCR / LLM) was added after most
    integration tests were written; those tests exercise upload/order/submit
    flows and never grant consent, so the gate would 403 them.  We no-op the
    gate globally here.  Tests that specifically verify the gate should mark
    themselves ``@pytest.mark.real_consent`` to run against the real logic.
    """
    if request.node.get_closest_marker("real_consent"):
        yield
        return

    from app.services.consent_service import ConsentService

    original = ConsentService.require_sensitive_processing

    async def _noop(self, user):  # noqa: ANN001, ANN202
        return None

    ConsentService.require_sensitive_processing = _noop  # type: ignore[assignment]
    try:
        yield
    finally:
        ConsentService.require_sensitive_processing = original  # type: ignore[assignment]


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


