"""
Security headers middleware — adds hardening HTTP headers to every response.

Applies:
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY          (clickjacking protection)
  - X-XSS-Protection: 1; mode=block
  - Referrer-Policy: strict-origin-when-cross-origin
  - Permissions-Policy: disable unneeded browser features
  - Content-Security-Policy: strict default; allowlist set via env

Import ordering: Starlette Middleware must be imported before Starlette Request.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Default CSP — restrictive default. Override via CSP_HEADER env var.
# Keys are space-separated; directives are semicolon-separated.
DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "   # Element Plus uses inline styles
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security headers into every HTTP response (including OPTIONS)."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # --- CORS-friendliness: OPTIONS must not be blocked by these headers ---
        # These headers are safe on OPTIONS and needed for preflight consistency.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy: disable unneeded browser APIs
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # Content-Security-Policy
        csp = DEFAULT_CSP
        response.headers["Content-Security-Policy"] = csp

        return response