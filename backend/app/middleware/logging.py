"""Request-logging middleware (loguru, single line per request)."""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger


_log = get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """One line per request, with timing + request id."""

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["x-request-id"] = rid
            return response
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            _log.info(
                "rid={} {} {} -> {} {:.1f}ms",
                rid,
                request.method,
                request.url.path,
                status,
                elapsed_ms,
            )
