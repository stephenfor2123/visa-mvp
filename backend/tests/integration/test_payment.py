"""Integration tests for /api/v2/payment/* — V2 §4.5 Payment Service (W6-2, Mock).

Covers (≥ 3 cases per W6-2 spec, 5 here):
  - test_payment_factory: get_payment_provider() returns the same singleton
  - test_create_order_mock: POST /payment/create returns trade_no + code_url +
    WxPay-shaped `weixin://wxpay/bizpayurl?pr=MOCKxxx` URL
  - test_notify_update_status: POST /payment/notify flips status → paid
  - test_payment_end_to_end: create → sleep 1.1s → GET /payment/{no} returns
    status="paid" (the auto-notify path is exercised end-to-end)
  - test_close_already_paid: 409 + code 4013 when closing a paid order

All tests share the same conftest as the other order/material tests
(import app.models at the top of the `app` fixture to register all
ORMs before create_all; monkeypatch stdlib time directly if needed).
"""
from __future__ import annotations

import asyncio
import io
import json
import re

import pytest

from app.core.db import AsyncSessionLocal
from app.models.destination import VisaDestination
from app.models.order import Order
from app.services.payment_provider import (
    PaymentProvider,
    get_payment_provider,
    reset_payment_provider_for_tests,
)
from sqlalchemy import select


# ----------------------------------------------------------------- #
# Helpers (mirror test_orders.py conventions)                        #
# ----------------------------------------------------------------- #
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG-PAYLOAD" * 32


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, phone: str) -> str:
    """Register or reuse account keyed by phone → returns access token."""
    uname = f"u{phone}"
    email = f"{phone}@test.local"
    pwd = "Test1234"
    send = await client.post(
        "/api/v2/auth/send-email-code",
        json={"email": email, "purpose": "register"},
    )
    assert send.status_code == 200, send.text
    email_code = send.json()["data"]["code"]
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": uname,
            "email": email,
            "password": pwd,
            "email_code": email_code,
        },
    )
    r = await client.post(
        "/api/v2/auth/login",
        json={"account": email, "password": pwd},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _upload_material(client, token: str, mat_type: str = "passport") -> int:
    files = {"file": (f"{mat_type}.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
    r = await client.post(
        "/api/v2/materials/upload",
        files=files,
        data={"material_type": mat_type},
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["material"]["id"]


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
                {"zh-CN": country_code, "en": country_code}, ensure_ascii=False
            ),
            visa_types=json.dumps(["tourism", "student"]),
            enabled=True,
            display_order=10,
        )
        s.add(dest)
        await s.commit()
        await s.refresh(dest)
        return dest.id


async def _create_order_for(
    client, token: str, dest_id: int, material_ids: list[int]
) -> str:
    r = await client.post(
        "/api/v2/orders",
        json={
            "destination_id": dest_id,
            "visa_type": "tourism",
            "material_ids": material_ids,
            "applicant_data": {"name": "Alice"},
        },
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["order_no"]


# ----------------------------------------------------------------- #
# Per-test setup: wipe the singleton + pending tasks between cases    #
# ----------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _reset_payment_singleton():
    """Each test starts with a clean PaymentProvider + empty notify queue."""
    reset_payment_provider_for_tests()
    yield
    reset_payment_provider_for_tests()


# ----------------------------------------------------------------- #
# Test cases                                                        #
# ----------------------------------------------------------------- #
class TestPaymentProviderFactory:
    def test_payment_factory_singleton(self):
        """get_payment_provider() returns the same instance per process
        so the pending-notify task map stays coherent across requests."""
        a = get_payment_provider()
        b = get_payment_provider()
        assert a is b
        assert isinstance(a, PaymentProvider)
        # Constants exposed for the API contract:
        assert PaymentProvider.AUTO_NOTIFY_DELAY_SECONDS == 1.0


class TestCreatePayment:
    async def test_create_order_mock_returns_trade_no_and_code_url(self, client):
        """POST /api/v2/payment/create → 201 + trade_no + WxPay-shaped code_url."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550001")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        r = await client.post(
            "/api/v2/payment/create",
            json={
                "order_no": order_no,
                "amount_cents": 19900,    # 199.00 USD
                "currency": "USD",
                "desc": "Schengen visa fee",
            },
            headers=_bearer(token),
        )
        assert r.status_code == 201, r.text
        body = r.json()["data"]
        assert body["order_no"] == order_no
        # trade_no is MOCK + 16 hex chars
        assert re.fullmatch(r"^MOCK[0-9A-F]{16}$", body["trade_no"]), body["trade_no"]
        # code_url shaped like WxPay bizpayurl with our MOCK prefix
        assert body["code_url"].startswith("weixin://wxpay/bizpayurl?pr=MOCK_"), body["code_url"]
        # Echo of the auto-notify contract for the front-end
        assert body["auto_notify_in_seconds"] == 1.0
        assert body["amount_cents"] == 19900
        assert body["currency"] == "USD"

    async def test_create_unauthenticated_1005(self, client):
        r = await client.post(
            "/api/v2/payment/create",
            json={
                "order_no": "V2-20260612-000001",
                "amount_cents": 100,
                "currency": "USD",
            },
        )
        assert r.status_code == 401
        assert r.json()["code"] == "1005"

    async def test_create_amount_zero_4014(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550002")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        r = await client.post(
            "/api/v2/payment/create",
            json={
                "order_no": order_no,
                "amount_cents": 0,
                "currency": "USD",
            },
            headers=_bearer(token),
        )
        # Pydantic's `gt=0` validator catches this at the schema layer
        # (1001 INVALID_PARAMS); the endpoint's deeper 4014 check is
        # belt-and-braces in case the schema ever loosens. Either is
        # the correct semantic answer: amount_cents must be > 0.
        assert r.status_code == 400
        assert r.json()["code"] in ("1001", "4014")

    async def test_create_other_users_order_4001(self, client):
        """Privacy: user A can't create a payment for user B's order."""
        dest_id = await _seed_destination("US")
        token_a = await _register(client, "13955550003")
        token_b = await _register(client, "13955550004")
        mid_a = await _upload_material(client, token_a)
        order_no = await _create_order_for(client, token_a, dest_id, [mid_a])

        r = await client.post(
            "/api/v2/payment/create",
            json={
                "order_no": order_no,
                "amount_cents": 100,
                "currency": "USD",
            },
            headers=_bearer(token_b),
        )
        # 4001 ORDER_NOT_FOUND (no existence leak across users)
        assert r.status_code == 404
        assert r.json()["code"] == "4001"


class TestNotifyPayment:
    async def test_notify_update_status_to_paid(self, client):
        """Direct hit: POST /payment/notify flips status pending → paid
        (idempotently — second call returns the same paid_at)."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550005")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        # Create the payment first (sets status=pending, schedules auto-notify).
        r1 = await client.post(
            "/api/v2/payment/create",
            json={
                "order_no": order_no,
                "amount_cents": 9900,
                "currency": "USD",
            },
            headers=_bearer(token),
        )
        assert r1.status_code == 201, r1.text
        trade_no = r1.json()["data"]["trade_no"]

        # Synchronously fire the notify endpoint BEFORE the auto-task does,
        # so we exercise the explicit callback path deterministically.
        r2 = await client.post(
            "/api/v2/payment/notify",
            json={"order_no": order_no, "trade_no": trade_no},
        )
        assert r2.status_code == 200, r2.text
        body = r2.json()["data"]
        assert body["status"] == "paid"
        assert body["trade_no"] == trade_no
        assert body["paid_at"] is not None

        # Idempotency: a second notify is a no-op (still 200, same trade_no).
        r3 = await client.post(
            "/api/v2/payment/notify",
            json={"order_no": order_no, "trade_no": trade_no},
        )
        assert r3.status_code == 200, r3.text
        assert r3.json()["data"]["trade_no"] == trade_no
        assert r3.json()["data"]["paid_at"] == body["paid_at"]

    async def test_notify_before_create_returns_4012(self, client):
        """Calling /notify for an order that never had /create → 404 / 4012."""
        r = await client.post(
            "/api/v2/payment/notify",
            json={"order_no": "V2-20260612-999999"},
        )
        assert r.status_code == 404
        assert r.json()["code"] == "4012"


class TestPaymentEndToEnd:
    async def test_create_then_auto_notify_paid(self, client):
        """Full W6-2 acceptance test:
            1. POST /payment/create → 201 + trade_no + code_url
            2. Immediately: GET /payment/{no} → status=pending
            3. Sleep 1.1s (past the auto-notify delay)
            4. GET /payment/{no} → status=paid (auto-notify fired)
        """
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550010")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        # 1) create
        rc = await client.post(
            "/api/v2/payment/create",
            json={
                "order_no": order_no,
                "amount_cents": 29900,
                "currency": "USD",
                "desc": "End-to-end payment test",
            },
            headers=_bearer(token),
        )
        assert rc.status_code == 201, rc.text
        trade_no = rc.json()["data"]["trade_no"]

        # 2) right after create: pending
        rq1 = await client.get(
            f"/api/v2/payment/{order_no}", headers=_bearer(token)
        )
        assert rq1.status_code == 200, rq1.text
        assert rq1.json()["data"]["status"] == "pending"
        assert rq1.json()["data"]["trade_no"] == trade_no

        # 3) wait past the 1s auto-notify delay
        await asyncio.sleep(1.2)

        # 4) after 1.2s: paid
        rq2 = await client.get(
            f"/api/v2/payment/{order_no}", headers=_bearer(token)
        )
        assert rq2.status_code == 200, rq2.text
        body = rq2.json()["data"]
        assert body["status"] == "paid", f"expected paid, got {body}"
        assert body["trade_no"] == trade_no
        assert body["paid_at"] is not None
        assert body["amount_cents"] == 29900


class TestClosePayment:
    async def test_close_pending_succeeds(self, client):
        """Cancel a still-pending payment before the auto-notify fires."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550020")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        rc = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 1000, "currency": "USD"},
            headers=_bearer(token),
        )
        assert rc.status_code == 201

        # Close BEFORE the auto-notify fires — we cancel the task in
        # close_order so it won't override us.
        rcl = await client.post(
            f"/api/v2/payment/{order_no}/close", headers=_bearer(token)
        )
        assert rcl.status_code == 200, rcl.text
        assert rcl.json()["data"]["status"] == "closed"

        # Subsequent GET should still report closed (and the auto-notify
        # task was cancelled in close_order, so it can't override us).
        await asyncio.sleep(1.2)
        rq = await client.get(
            f"/api/v2/payment/{order_no}", headers=_bearer(token)
        )
        assert rq.status_code == 200
        assert rq.json()["data"]["status"] == "closed"

    async def test_close_already_paid_4013(self, client):
        """Close on a paid order is refused — refund (V2.1) is the right path."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550021")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        # create + manually notify → paid
        rc = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 1000, "currency": "USD"},
            headers=_bearer(token),
        )
        assert rc.status_code == 201
        trade_no = rc.json()["data"]["trade_no"]
        rn = await client.post(
            "/api/v2/payment/notify",
            json={"order_no": order_no, "trade_no": trade_no},
        )
        assert rn.status_code == 200

        # Try to close a paid order
        rcl = await client.post(
            f"/api/v2/payment/{order_no}/close", headers=_bearer(token)
        )
        assert rcl.status_code == 409
        assert rcl.json()["code"] == "4013"

    async def test_close_no_payment_record_4012(self, client):
        """Closing an order that never had /create → 404 / 4012."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550022")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        rcl = await client.post(
            f"/api/v2/payment/{order_no}/close", headers=_bearer(token)
        )
        assert rcl.status_code == 404
        assert rcl.json()["code"] == "4012"


class TestRefundPayment:
    async def test_refund_paid_order_mock(self, client):
        """POST /payment/{no}/refund flips paid → refunded (mock channel)."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550030")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        rc = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 1990, "currency": "USD"},
            headers=_bearer(token),
        )
        assert rc.status_code == 201, rc.text
        trade_no = rc.json()["data"]["trade_no"]
        rn = await client.post(
            "/api/v2/payment/notify",
            json={"order_no": order_no, "trade_no": trade_no},
        )
        assert rn.status_code == 200, rn.text

        rr = await client.post(
            f"/api/v2/payment/{order_no}/refund",
            json={"reason": "user cancelled within policy"},
            headers=_bearer(token),
        )
        assert rr.status_code == 200, rr.text
        body = rr.json()["data"]
        assert body["status"] == "refunded"
        assert body["refund_trade_no"].startswith("REFUND")
        assert body["refund_amount_cents"] == 1990

        rq = await client.get(
            f"/api/v2/payment/{order_no}", headers=_bearer(token)
        )
        assert rq.status_code == 200, rq.text
        assert rq.json()["data"]["status"] == "refunded"
        assert rq.json()["data"]["refund_trade_no"] == body["refund_trade_no"]

    async def test_refund_pending_order_4014(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550031")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        rc = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 1000, "currency": "USD"},
            headers=_bearer(token),
        )
        assert rc.status_code == 201

        rr = await client.post(
            f"/api/v2/payment/{order_no}/refund",
            json={},
            headers=_bearer(token),
        )
        assert rr.status_code == 400
        assert rr.json()["code"] == "4014"


class TestPaymentIdempotency:
    async def test_create_idempotent_returns_same_trade_no(self, client):
        """Duplicate create while pending + same amount → same trade_no."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550040")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        payload = {"order_no": order_no, "amount_cents": 1990, "currency": "USD"}
        r1 = await client.post(
            "/api/v2/payment/create", json=payload, headers=_bearer(token)
        )
        r2 = await client.post(
            "/api/v2/payment/create", json=payload, headers=_bearer(token)
        )
        assert r1.status_code == 201, r1.text
        assert r2.status_code == 201, r2.text
        assert r1.json()["data"]["trade_no"] == r2.json()["data"]["trade_no"]

    async def test_create_when_already_paid_4013(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550041")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        rc = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 1000, "currency": "USD"},
            headers=_bearer(token),
        )
        trade_no = rc.json()["data"]["trade_no"]
        await client.post(
            "/api/v2/payment/notify",
            json={"order_no": order_no, "trade_no": trade_no},
        )

        r2 = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 1000, "currency": "USD"},
            headers=_bearer(token),
        )
        assert r2.status_code == 409
        assert r2.json()["code"] == "4013"

    async def test_notify_stale_trade_no_rejected(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550042")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        rc = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 1000, "currency": "USD"},
            headers=_bearer(token),
        )
        assert rc.status_code == 201
        # Supersede with different amount → new trade_no
        rc2 = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 2000, "currency": "USD"},
            headers=_bearer(token),
        )
        assert rc2.status_code == 201
        assert rc2.json()["data"]["trade_no"] != rc.json()["data"]["trade_no"]

        stale = await client.post(
            "/api/v2/payment/notify",
            json={
                "order_no": order_no,
                "trade_no": rc.json()["data"]["trade_no"],
            },
        )
        assert stale.status_code == 404
        assert stale.json()["code"] == "4012"

    async def test_refund_idempotent_second_call(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550043")
        mid = await _upload_material(client, token)
        order_no = await _create_order_for(client, token, dest_id, [mid])

        rc = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 1500, "currency": "USD"},
            headers=_bearer(token),
        )
        trade_no = rc.json()["data"]["trade_no"]
        await client.post(
            "/api/v2/payment/notify",
            json={"order_no": order_no, "trade_no": trade_no},
        )
        r1 = await client.post(
            f"/api/v2/payment/{order_no}/refund",
            json={},
            headers=_bearer(token),
        )
        r2 = await client.post(
            f"/api/v2/payment/{order_no}/refund",
            json={},
            headers=_bearer(token),
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert (
            r1.json()["data"]["refund_trade_no"]
            == r2.json()["data"]["refund_trade_no"]
        )