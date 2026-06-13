"""/ws/orders/{order_no} — V2 §4.2.4 (Story 3.2.1a, cycle 3 full scope).

Real WebSocket endpoint. JWT auth via ?token=, then a keep-alive loop
with a *broadcast* push from PollService: any state change goes
through ConnectionManager → all WS subscribers of that order_no.

Cycle 3 close-out (W3-NO-DEFER): WSBroadcaster + ConnectionManager
registry wired in. Frontend api/orders.js:402 env swap landed.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.security import TOKEN_TYPE_ACCESS, decode_token


router = APIRouter()

PING_INTERVAL_S = 30.0
PONG_TIMEOUT_S = 60.0


class ConnectionManager:
    """In-process WS subscriber registry keyed by order_no.

    `connect()` accepts the WS then registers it. `disconnect()` is
    idempotent and safe to call on an unknown socket. `broadcast()`
    fans a JSON message out to every live subscriber; dead sockets
    are auto-pruned.

    Single-process scope is intentional: future multi-worker will
    swap the dict for a Redis pub/sub bridge. The interface stays.
    """

    def __init__(self) -> None:
        self._subs: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, order_no: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._subs.setdefault(order_no, set()).add(ws)

    async def disconnect(self, order_no: str, ws: WebSocket) -> None:
        async with self._lock:
            subs = self._subs.get(order_no)
            if subs and ws in subs:
                subs.discard(ws)
                if not subs:
                    self._subs.pop(order_no, None)

    async def broadcast(self, order_no: str, message: dict[str, Any]) -> None:
        # Snapshot the live subscriber list under the lock, then send
        # outside it so a slow client can't block registration of
        # other order_no's.
        async with self._lock:
            subs = list(self._subs.get(order_no, ()))
        if not subs:
            return
        dead: list[WebSocket] = []
        for ws in subs:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                live = self._subs.get(order_no)
                if live is not None:
                    for ws in dead:
                        live.discard(ws)
                    if not live:
                        self._subs.pop(order_no, None)

    def subscribers(self, order_no: str) -> int:
        """Test-only: how many WSs are currently subscribed to order_no."""
        return len(self._subs.get(order_no, ()))


# Module-level singleton (the only instance used by the app + tests).
connection_manager = ConnectionManager()


def _resolve_user_id(token: Optional[str]) -> Optional[int]:
    """Validate JWT, return user_id (int) or None on any failure."""
    if not token:
        return None
    try:
        payload = decode_token(token, TOKEN_TYPE_ACCESS)
        return int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError, Exception):
        return None


@router.websocket("/orders/{order_no}")
async def ws_order_status(
    websocket: WebSocket,
    order_no: str,
    token: Optional[str] = Query(None),
) -> None:
    """Auth-gated broadcast + keep-alive endpoint. Close 1008 on auth fail."""
    user_id = _resolve_user_id(token)
    if user_id is None:
        await websocket.close(code=1008)
        return
    await connection_manager.connect(order_no, websocket)
    last_recv = time.monotonic()
    try:
        # Greet the freshly-connected client with the current state
        # envelope so the UI knows "you're subscribed".
        await websocket.send_json(
            {"type": "ready", "data": {"order_no": order_no}}
        )
        while True:
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_text(), timeout=PING_INTERVAL_S
                )
                last_recv = time.monotonic()
            except asyncio.TimeoutError:
                now = time.monotonic()
                if now - last_recv > PONG_TIMEOUT_S:
                    await websocket.close(code=1008)
                    break
                await websocket.send_json({"type": "ping", "ts": int(time.time())})
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(order_no, websocket)


__all__ = ["router", "ConnectionManager", "connection_manager"]
