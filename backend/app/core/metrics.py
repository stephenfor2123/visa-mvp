"""
Prometheus metrics — request_count, request_duration_ms, active_users.

Exposed via GET /metrics in main.py.
"""
import time
from functools import wraps
from typing import Callable, Any

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST


# ── Request-level ──────────────────────────────────────────────────────────── #

request_count = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

request_duration_ms = Histogram(
    "http_request_duration_ms",
    "HTTP request duration in milliseconds",
    ["method", "endpoint"],
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000),
)

# ── Business-level ─────────────────────────────────────────────────────────── #

active_users = Gauge(
    "app_active_users",
    "Number of users with an active session (authenticated via JWT)",
)


# ── Decorator ─────────────────────────────────────────────────────────────── #

def timed(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that records duration_ms for a route handler."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        # Attempt to extract method/endpoint from kwargs (FastAPI injects Request)
        endpoint = getattr(func, "__name__", "unknown")
        request_duration_ms.labels(method="POST", endpoint=endpoint).observe(elapsed_ms)
        return result

    return wrapper


def record_request(method: str, endpoint: str, status_code: int) -> None:
    """Call after a request is processed to increment the counter."""
    request_count.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()


def metrics_bytes() -> bytes:
    """Return Prometheus-formatted metrics payload."""
    return generate_latest()


METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST