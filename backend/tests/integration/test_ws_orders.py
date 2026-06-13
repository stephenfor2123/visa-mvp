"""Story 3.2.1a — WS endpoint tests (cycle-3 scope).

Two cases:
  - test_ws_auth_required                no/garbage token → 1008
  - test_ws_broadcast_on_poll_tick       valid token → PollService.record_change
                                         triggers {type:'status', data:{...}} push
"""
from __future__ import annotations

import asyncio
import json
import secrets
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx_ws import WebSocketDisconnect, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.destination import VisaDestination
from app.models.order import Order
from app.services.poll_service import PollService


@pytest_asyncio.fixture()
async def asgi_client(app):
    """ASGI client with WS upgrade support (httpx-ws)."""
    transport = ASGIWebSocketTransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ----------------------------------------------------------------------- #
# Helpers — mirror test_poll.py patterns (no cross-test coupling).         #
# ----------------------------------------------------------------------- #
async def _register(client, phone: str) -> str:
    r = await client.post(
        "/api/v2/auth/sms-login",
        json={"phone": phone, "phone_country": "+86", "sms_code": "123456"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _seed_destination(country_code: str = "US") -> int:
    async with AsyncSessionLocal() as s:
        existing = await s.scalar(
            select(VisaDestination).where(
                VisaDestination.country_code == country_code
            )
        )
        if existing is not None:
            return existing.id
        dest = VisaDestination(
            country_code=country_code,
            country_name_i18n=json.dumps(
                {"zh-CN": "美国", "en": "United States"}, ensure_ascii=False
            ),
            visa_types=json.dumps(["tourism", "student"]),
            enabled=True,
            display_order=10,
        )
        s.add(dest)
        await s.commit()
        await s.refresh(dest)
        return dest.id


async def _create_order(user_id: int, dest_id: int, *, order_no: str) -> int:
    async with AsyncSessionLocal() as s:
        order = Order(
            order_no=order_no,
            user_id=user_id,
            destination_id=dest_id,
            visa_type="tourism",
            status="submitted",
        )
        s.add(order)
        await s.commit()
        await s.refresh(order)
        return order.id


async def _resolve_user_id(client, token: str) -> int:
    """Decode the access token by re-using the security helper."""
    from app.core.security import TOKEN_TYPE_ACCESS, decode_token

    return int(decode_token(token, TOKEN_TYPE_ACCESS)["sub"])


# ----------------------------------------------------------------------- #
# Tests                                                                    #
# ----------------------------------------------------------------------- #
class TestWSAuth:
    async def test_ws_auth_required(self, asgi_client):
        """No token / garbage token → server closes with 1008."""
        url = "ws://test/ws/orders/V2-DOES-NOT-MATTER"
        with pytest.raises(WebSocketDisconnect) as exc_info:
            async with aconnect_ws(url, client=asgi_client) as ws:
                await ws.receive_text()
        assert exc_info.value.code == 1008

        url2 = f"{url}?token={secrets.token_hex(16)}"
        with pytest.raises(WebSocketDisconnect) as exc_info2:
            async with aconnect_ws(url2, client=asgi_client) as ws:
                await ws.receive_text()
        assert exc_info2.value.code == 1008


class TestWSBroadcast:
    async def test_ws_broadcast_on_poll_tick(
        self, asgi_client, monkeypatch
    ):
        """Valid WS subscription receives a status push when PollService
        records a committed change on the same order_no.

        Flow:
          1) register user → JWT
          2) seed destination + create one `submitted` order
          3) monkeypatch poll_service._broadcast_to_ws_subscribers to
             await connection_manager.broadcast() INLINE (no
             loop.create_task) — otherwise the fire-and-forget task
             runs in a different task than the WS, and pytest-asyncio's
             per-test loop scope creates an anyio cancel-scope mismatch
             at fixture teardown.
          4) open WS → receive "ready" → record_change → receive push
          5) assert envelope
        """
        # 0) Replace the fire-and-forget broadcast with a synchronous
        # await so the test runs in one task boundary.
        from app.api.v2 import ws_orders as ws_mod
        from app.services import poll_service

        async def _sync_broadcast(
            order_no, *, status_after, status_before, poll_source, polled_at
        ):
            await ws_mod.connection_manager.broadcast(
                order_no,
                {
                    "type": "status",
                    "data": {
                        "order_no": order_no,
                        "status": status_after,
                        "status_before": status_before,
                        "poll_source": poll_source,
                        "polled_at": polled_at.isoformat() if polled_at else None,
                    },
                },
            )

        monkeypatch.setattr(
            poll_service, "_broadcast_to_ws_subscribers", _sync_broadcast
        )

        # 1) Register
        token = await _register(asgi_client, "13900001111")
        user_id = await _resolve_user_id(asgi_client, token)

        # 2) Seed dest + order
        dest_id = await _seed_destination("US")
        order_no = "V2-WSBROAD-0001"
        await _create_order(user_id, dest_id, order_no=order_no)

        # 3) Open WS in same task boundary
        url = f"ws://test/ws/orders/{order_no}?token={token}"

        async with aconnect_ws(url, client=asgi_client) as ws:
            # 3a) Welcome frame
            first = await ws.receive_json()
            assert first["type"] == "ready", first
            assert first["data"]["order_no"] == order_no

            # 3b) Trigger the change — broadcast runs INLINE (same task)
            async with AsyncSessionLocal() as s:
                order = (
                    await s.execute(
                        select(Order).where(Order.order_no == order_no)
                    )
                ).scalar_one()
                svc = PollService(s)
                await svc.record_change(
                    order=order,
                    status_before="submitted",
                    status_after="reviewing",
                    poll_source="rpa_callback",
                    polled_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    notes="test broadcast",
                    commit=True,
                )

            # 3c) Receive the broadcast (delivered inline above)
            msg = await asyncio.wait_for(ws.receive_json(), timeout=2.0)

        # 4) Assertions
        assert msg["type"] == "status", msg
        assert msg["data"]["order_no"] == order_no
        assert msg["data"]["status"] == "reviewing"
        assert msg["data"]["status_before"] == "submitted"
        assert msg["data"]["poll_source"] == "rpa_callback"
        assert msg["data"]["polled_at"]  # ISO-8601 string present
