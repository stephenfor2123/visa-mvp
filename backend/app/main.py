"""
Visa MVP — FastAPI application entry point.

Run locally:
    cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

Run with Docker:
    cd backend && docker compose up --build
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v2 import api_v2_router
from app.api.v2 import scheduler as scheduler_router
from app.api.v2 import ws_orders as ws_router
from app.core.config import get_settings
from app.core.db import engine
from app.core.errors import BizException, ErrorCode, build_error_payload
from app.core.logging import configure_logging, get_logger
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure logging + verify DB connection on startup."""
    configure_logging()
    log = get_logger()
    settings = get_settings()
    log.info("starting {} v{}", settings.app_name, settings.app_version)
    # Verify DB connectivity so we fail fast if config is broken.
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("db connection OK ({})", settings.database_url)
    except Exception as exc:  # pragma: no cover - depends on environment
        log.error("db connection FAILED: {}", exc)
        raise
    yield
    log.info("shutting down")
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    log = get_logger()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Visa MVP API (V2) — Auth, Orders, Materials, RPA, Payments.",
        lifespan=lifespan,
    )

    # --- CORS (dev-friendly; tighten in prod) ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Request logging ---
    app.add_middleware(RequestLoggingMiddleware)

    # --- Rate limiting (per-IP, per route class) ---
    app.add_middleware(
        RateLimitMiddleware,
        global_per_min=settings.rate_limit_per_ip_per_min,
        slow_per_min=settings.rate_limit_slow_api_per_ip_per_min,
    )

    # --- Routers ---
    app.include_router(api_v2_router, prefix=settings.api_prefix)

    # Scheduler endpoints live OUTSIDE /api/v2 by design — they're
    # internal, use shared-secret auth (X-System-Key), and shouldn't
    # share rate-limit or JWT middleware semantics with user APIs.
    app.include_router(scheduler_router.router, prefix="/scheduler")

    # Story 3.2.1a — minimal WS endpoint at /ws/orders/{order_no}.
    # Lives outside /api/v2 to match the URL the front-end constructs
    # (api/orders.js polls fallback; WS upgrade target is /ws/...).
    app.include_router(ws_router.router, prefix="/ws")

    # --- Health ---
    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "app": settings.app_name, "version": settings.app_version}

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "api": settings.api_prefix,
        }

    # --- Exception handlers (uniform error envelope) ---
    @app.exception_handler(BizException)
    async def _biz_handler(_: Request, exc: BizException) -> JSONResponse:
        log.warning("biz error code={} msg={}", exc.code.value, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_payload(exc.code, exc.message, exc.data),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic 422 -> V2 1001 INVALID_PARAMS.
        # `errors()` may contain non-JSON-serializable objects (e.g. ValueError
        # instances raised inside field validators). Sanitize to str.
        log.info("validation error: {}", exc.errors())
        safe_errors = []
        for err in exc.errors():
            safe = {k: (str(v) if k == "ctx" and v is not None else v) for k, v in err.items()}
            # ctx can still have non-serializable values — flatten to strings
            if isinstance(safe.get("ctx"), dict):
                safe["ctx"] = {ck: str(cv) for ck, cv in safe["ctx"].items()}
            safe_errors.append(safe)
        return JSONResponse(
            status_code=400,
            content=build_error_payload(
                ErrorCode.INVALID_PARAMS,
                message="Invalid request parameters",
                data={"errors": safe_errors},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled: {}", exc)
        return JSONResponse(
            status_code=500,
            content=build_error_payload(ErrorCode.SERVER_ERROR, message="Internal server error"),
        )

    log.info("app created (env={} api_prefix={})", settings.env, settings.api_prefix)
    return app


# uvicorn entry-point
app = create_app()
