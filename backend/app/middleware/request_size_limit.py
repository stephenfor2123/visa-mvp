"""
Request body size limit middleware.

Rejects requests with Content-Length exceeding max_size_mb.
The actual body reading is delegated to FastAPI/Pydantic downstream;
this middleware fails fast before any parsing to avoid memory exhaustion.
"""
from __future__ import annotations
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Enforce max request body size; return 413 if exceeded."""

    def __init__(self, app, max_size_mb:Optional[int]= None):
        super().__init__(app)
        self.max_bytes: int = (max_size_mb or get_settings().max_request_size_mb) * 1024 * 1024

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": (
                                f"Request body exceeds maximum allowed size "
                                f"({self.max_bytes // (1024 * 1024)} MB)."
                            ),
                        },
                    )
            except ValueError:
                pass  # malformed header — let downstream handle it

        response = await call_next(request)
        return response