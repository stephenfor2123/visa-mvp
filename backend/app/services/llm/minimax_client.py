"""MiniMax chat completion client (W40 — itinerary auto-generation).

SECURITY: `minimax_api_key` is a secret, read from Settings (.env, gitignored).
Never log the key or echo it in error messages.

Reliability notes (W47b — production observability):
  - MiniMax's public endpoint is flaky: in dev logs we saw responses anywhere
    from 5s to 57s, plus intermittent ConnectError / RemoteProtocolError with
    EMPTY `str(exc)` (httpx exception has no message — only the class name).
    The previous code only formatted `str(exc)`, so users saw
    "network error calling MiniMax: " with nothing after the colon, which is
    impossible to triage.
  - Fix: format exceptions as `type(exc).__name__ + " · " + (str or repr) +
    " · cause=" + repr(__cause__)`. Also auto-retry once on transient network
    failures (NOT on upstream MiniMax error responses, which carry a real
    `base_resp.status_code` — those won't fix themselves by retrying).
  - Force HTTP/1.1: MiniMax's LB strips HTTP/2 and httpx falls back mid-stream
    which can present as `RemoteProtocolError`. Forcing http1 makes the
    failure mode predictable.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import get_settings

_log = logging.getLogger(__name__)


def _fmt_exc(exc: BaseException) -> str:
    """Format an exception for error messages, surviving httpx's empty str(exc).

    httpx exceptions like ConnectError / RemoteProtocolError have an empty
    `str(exc)` — only the class name is useful. We always include the class,
    and append `str(exc)` / `repr(exc)` (whichever has content), plus a one-line
    cause if there's a chained exception.
    """
    cls = type(exc).__name__
    s = str(exc).strip()
    r = repr(exc).strip()
    # Pick whichever representation actually has visible text.
    detail = s if s and s != cls else (r if r and r not in (cls, f"{cls}()") else "")
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    cause_str = f" · cause={type(cause).__name__}: {cause}" if cause else ""
    return f"{cls}{(': ' + detail) if detail else ''}{cause_str}"


class MiniMaxError(RuntimeError):
    """Raised on any MiniMax call failure (missing key, network, non-zero status_code)."""


class MiniMaxClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.minimax_api_key
        self.api_base = settings.minimax_api_base.rstrip("/")
        self.model = settings.minimax_model

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def chat(self, messages: list[dict], *, temperature: float = 0.7, timeout: float = 25.0) -> str:
        """Send a chat completion request, return the assistant's text content.

        Raises MiniMaxError on missing config, network failure, or a non-zero
        `base_resp.status_code` in the response body (MiniMax's own error
        signal — HTTP 200 is returned even for errors like "insufficient
        balance", so we must check the body, not just the status code).

        Reliability:
          - 25s per-attempt timeout (down from 45s). 45s is past user patience
            for an interactive "Generate Itinerary" button; if MiniMax can't
            answer in 25s, a retry is more useful than waiting longer.
          - 1 automatic retry on transient network errors (ConnectError,
            RemoteProtocolError, ReadTimeout, WriteTimeout, PoolTimeout,
            ConnectTimeout, httpcore errors). NOT on MiniMax business-error
            responses (those won't fix themselves).
          - Force HTTP/1.1 to avoid mid-stream HTTP/2 fallback errors.
        """
        if not self.configured:
            raise MiniMaxError("MiniMax API key not configured")

        url = f"{self.api_base}/text/chatcompletion_v2"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Errors worth retrying: network-layer / transport-layer only.
        # Anything else (JSON decode error, business status_code) is a real
        # response from MiniMax — retrying won't change the answer.
        retryable = (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.RemoteProtocolError,
            httpx.LocalProtocolError,
            httpx.NetworkError,
            httpx.ProxyError,
            httpx.UnsupportedProtocol,
        )

        last_exc: BaseException | None = None
        for attempt in (1, 2):
            try:
                # http1=True → no HTTP/2 negotiation; MiniMax's LB has shown
                # HTTP/2 SETTINGS frame dropouts that surface as
                # RemoteProtocolError("") after ~10s of streaming.
                async with httpx.AsyncClient(timeout=timeout, http2=False) as client:
                    resp = await client.post(url, headers=headers, json=body)
            except retryable as exc:
                last_exc = exc
                _log.warning(
                    "MiniMax call attempt %d/2 failed (%s); %s",
                    attempt, _fmt_exc(exc),
                    "retrying once" if attempt == 1 else "giving up",
                )
                if attempt == 2:
                    raise MiniMaxError(f"network error calling MiniMax: {_fmt_exc(exc)}") from exc
                # Brief backoff before retry — 0.8s is enough to ride out a
                # transient TCP reset / DNS hiccup.
                await asyncio.sleep(0.8)
                continue
            except httpx.HTTPError as exc:
                # Non-retryable httpx error (rare — usually wrapped above).
                raise MiniMaxError(f"network error calling MiniMax: {_fmt_exc(exc)}") from exc

            # Got an HTTP response. Decode + validate body.
            try:
                data = resp.json()
            except ValueError as exc:
                raise MiniMaxError(
                    f"MiniMax returned non-JSON response (HTTP {resp.status_code}, "
                    f"body[:200]={resp.text[:200]!r})"
                ) from exc

            base_resp = data.get("base_resp") or {}
            status_code = base_resp.get("status_code", 0)
            if status_code:
                raise MiniMaxError(f"MiniMax error {status_code}: {base_resp.get('status_msg', 'unknown')}")

            choices = data.get("choices") or []
            if not choices:
                raise MiniMaxError("MiniMax returned no choices")
            message = choices[0].get("message") or {}
            content = message.get("content")
            if not content:
                raise MiniMaxError("MiniMax returned an empty message")
            return content

        # Defensive — loop above always either returns or raises.
        raise MiniMaxError(f"network error calling MiniMax: {_fmt_exc(last_exc) if last_exc else 'unknown'}")


_client: MiniMaxClient | None = None


def get_minimax_client() -> MiniMaxClient:
    global _client
    if _client is None:
        _client = MiniMaxClient()
    return _client
