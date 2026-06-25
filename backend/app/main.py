"""
Htex — FastAPI application entry point.

Run locally:
    cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

Run with Docker:
    cd backend && docker compose up --build
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
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
from app.core.metrics import metrics_bytes, METRICS_CONTENT_TYPE
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_size_limit import RequestSizeLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware


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
    # Refuse to boot in prod with the dev-only placeholder password.
    if settings.env == "prod" and settings.admin_password == "CHANGE_ME_IN_PROD":
        raise ValueError(
            "ADMIN_PASSWORD is still the dev placeholder. "
            "Set ADMIN_PASSWORD env var before deploying to prod."
        )
    # Refuse to boot in prod with the dev-only placeholder JWT secret.
    if settings.env == "prod" and settings.jwt_secret == "dev-secret-change-me-in-prod-visa-mvp-2026":
        raise ValueError(
            "JWT_SECRET is still the dev placeholder. "
            "Set JWT_SECRET env var before deploying to prod."
        )
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
        description="Htex API (V2) — Auth, Orders, Materials, RPA, Payments.",
        lifespan=lifespan,
    )

    # --- Security headers (X-Content-Type-Options, CSP, X-Frame-Options, etc.) ---
    app.add_middleware(SecurityHeadersMiddleware)

    # --- Request body size limit (max 10 MB, configurable via MAX_REQUEST_SIZE_MB) ---
    app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=settings.max_request_size_mb)

    # --- CORS (tightened: explicit allowlist, no wildcard in prod) ---
    # Origins are parsed from CORS_ALLOWED_ORIGINS env var (comma-separated).
    # Dev default covers localhost:5173 (Vite), :4173 (preview), :3000 ( CRA).
    # In prod, set CORS_ALLOWED_ORIGINS to the exact frontend domain(s).
    allowed_origins = [
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ]
    if not allowed_origins:
        raise ValueError(
            "CORS_ALLOWED_ORIGINS must be set (at least one origin). "
            "In dev: http://localhost:5173. In prod: your frontend domain."
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-System-Key",
            "X-Requested-With",
            "Accept-Language",
        ],
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

    # --- Health (with DB ping) ---
    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        db_ok = False
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception as exc:
            log.warning("health check db ping failed: {}", exc)
        return {
            "status": "ok" if db_ok else "degraded",
            "db_ok": db_ok,
            "version": settings.app_version,
        }

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "api": settings.api_prefix,
        }

    # --- Metrics (Prometheus scrape target) ---
    @app.get("/metrics", tags=["meta"], include_in_schema=False)
    async def metrics():
        from starlette.responses import Response
        return Response(content=metrics_bytes(), media_type=METRICS_CONTENT_TYPE)

    # --- Exception handlers (uniform error envelope) ---
    @app.exception_handler(BizException)
    async def _biz_handler(_: Request, exc: BizException) -> JSONResponse:
        log.warning("biz error code={} msg={}", exc.code.value, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_payload(exc.code, exc.message, exc.data),
        )

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        """Catch-all for any remaining raw HTTPException (bypass-safe fallback)."""
        log.warning("http exception status={} detail={}", exc.status_code, exc.detail)
        # Map common status codes to our ErrorCode equivalents.
        code_map = {
            status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN,
            status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
            status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMIT,
        }
        code = code_map.get(exc.status_code, ErrorCode.SERVER_ERROR)
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_payload(code, message=detail),
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
