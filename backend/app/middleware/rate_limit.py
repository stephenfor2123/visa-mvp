"""In-memory sliding-window rate limiter (per-IP, per-route class).

V2 §9.4 limits:
  - global: 100 req/min/IP
  - slow API: 60 req/min/IP   (auth, send-code, login)
  - sms send: 1/60s + 10/day  (handled inside SmsService)

This is intentionally in-memory: W1 runs on a single uvicorn worker.
A real cluster would back this with Redis (interface kept simple enough
to swap).
"""
from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.errors import ErrorCode, build_error_payload


class InMemoryRateLimiter:
    """Per-key sliding window. Key is (route_class, client_ip)."""

    def __init__(self) -> None:
        # key -> deque[timestamp_ms]
        self._buckets: Dict[Tuple[str, str], Deque[float]] = {}

    def hit(self, key: Tuple[str, str], limit: int, window_s: int = 60) -> bool:
        now_ms = time.time() * 1000
        cutoff = now_ms - window_s * 1000
        bucket = self._buckets.setdefault(key, deque())
        # Drop expired
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now_ms)
        return True


# Suffixes considered "slow" — V2 §9.4 (60 req/min/IP)
_SLOW_PREFIXES = ("/api/v2/auth",)


def _classify(path: str) -> str:
    for prefix in _SLOW_PREFIXES:
        if path.startswith(prefix):
            return "slow"
    return "global"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware: returns 429 on rate-limit hit."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        limiter: InMemoryRateLimiter | None = None,
        global_per_min: int = 100,
        slow_per_min: int = 60,
    ) -> None:
        super().__init__(app)
        self.limiter = limiter or InMemoryRateLimiter()
        self.global_per_min = global_per_min
        self.slow_per_min = slow_per_min

    async def dispatch(self, request: Request, call_next) -> Response:
        # Don't rate-limit health/docs
        if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        # X-Forwarded-For wins when behind a proxy (ngrok / cloudflared)
        xff = request.headers.get("x-forwarded-for")
        if xff:
            client_ip = xff.split(",")[0].strip()

        route_class = _classify(request.url.path)
        limit = self.slow_per_min if route_class == "slow" else self.global_per_min

        if not self.limiter.hit((route_class, client_ip), limit=limit, window_s=60):
            return JSONResponse(
                status_code=429,
                content=build_error_payload(
                    ErrorCode.RATE_LIMIT,
                    message=f"Rate limit exceeded: {limit} req/min ({route_class})",
                    data={"route_class": route_class, "limit": limit},
                ),
            )
        return await call_next(request)
