#!/usr/bin/env python3
"""Local Stripe Phase A smoke test — no Stripe CLI required.

Uses GET /payment/{order_no} polling sync when webhook is not configured.
Run with backend on http://127.0.0.1:8000 and PAYMENT_CHANNEL=stripe in .env.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time
import uuid

import httpx

BASE = os.environ.get("HTEX_API_BASE", "http://127.0.0.1:8000/api/v2")
JPEG = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG" * 32


def _ok(r: httpx.Response, step: str) -> dict:
    if r.status_code >= 400:
        print(f"FAIL [{step}] {r.status_code}: {r.text[:500]}")
        sys.exit(1)
    body = r.json()
    if body.get("code") not in (None, "1000"):
        print(f"FAIL [{step}] biz code {body.get('code')}: {body}")
        sys.exit(1)
    return body.get("data") or body


async def main() -> None:
    suffix = uuid.uuid4().hex[:8]
    email = f"stripe-e2e-{suffix}@test.local"
    password = "Test1234!"
    username = f"stripe{suffix}"

    async with httpx.AsyncClient(base_url=BASE, timeout=60.0) as client:
        # health
        h = await client.get(BASE.replace("/api/v2", "") + "/health")
        h.raise_for_status()
        print("OK health", h.json())

        cfg = _ok(await client.get("/payment/config"), "payment/config")
        assert cfg.get("channel") == "stripe", f"expected stripe, got {cfg}"
        print("OK payment channel = stripe")

        login = _ok(
            await client.post(
                "/auth/login",
                json={"account": "demo138001380002@htex.app", "password": "Htex@2026"},
            ),
            "login",
        )
        token = login["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("OK login demo user")

        orders = _ok(await client.get("/orders", headers=headers), "orders/list")
        items = orders.get("items") or orders
        if isinstance(items, dict):
            items = items.get("items", [])
        pending = next(
            (o for o in items if o.get("status") in ("created", "pending") and not o.get("paid")),
            None,
        )
        if pending:
            order_no = pending["order_no"]
            amount_cents = int(float(pending.get("total_amount") or 0) * 100)
            print("OK reuse order", order_no, "amount_cents", amount_cents)
        else:
            dests = _ok(await client.get("/destinations"), "destinations")
            dest_id = dests[0]["id"]

            proc = _ok(
                await client.post(
                    "/materials/process",
                    files={"file": ("passport.jpg", io.BytesIO(JPEG), "image/jpeg")},
                    data={"material_type": "passport"},
                    headers=headers,
                ),
                "materials/process",
            )
            mat_id = proc["material"]["id"]

            order = _ok(
                await client.post(
                    "/orders",
                    json={
                        "destination_id": dest_id,
                        "visa_type": "tourism",
                        "material_ids": [mat_id],
                        "applicant_data": {"name": "Stripe E2E"},
                    },
                    headers=headers,
                ),
                "orders/create",
            )
            order_no = order["order_no"]
            pricing = _ok(await client.get("/pricing/current"), "pricing/current")
            amount_cents = int(pricing["display_price_cents"])
            print("OK new order", order_no, "amount_cents", amount_cents)

        if amount_cents <= 0:
            pricing = _ok(await client.get("/pricing/current"), "pricing/current")
            amount_cents = int(pricing["display_price_cents"])

        created = _ok(
            await client.post(
                "/payment/create",
                json={
                    "order_no": order_no,
                    "amount_cents": amount_cents,
                    "currency": "USD",
                    "desc": "platform fee",
                },
                headers=headers,
            ),
            "payment/create",
        )
        trade_no = created["trade_no"]
        client_secret = created.get("client_secret") or created.get("prepay_id")
        assert trade_no and client_secret, created
        print("OK payment create", trade_no)

        # Confirm via Stripe SDK (test card)
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from app.core.config import get_settings
        import stripe

        settings = get_settings()
        stripe.api_key = settings.stripe_secret_key
        intent = stripe.PaymentIntent.confirm(
            trade_no,
            payment_method="pm_card_visa",
            return_url="http://127.0.0.1:5173/",
        )
        assert intent.status == "succeeded", intent.status
        print("OK stripe PaymentIntent succeeded")

        # Poll our API — syncs paid without webhook
        paid = False
        for _ in range(10):
            q = _ok(
                await client.get(f"/payment/{order_no}", headers=headers),
                "payment/query",
            )
            if q.get("status") == "paid":
                paid = True
                print("OK order payment status = paid", q.get("paid_at"))
                break
            await asyncio.sleep(0.5)
        if not paid:
            print("FAIL payment did not sync to paid within 5s")
            sys.exit(1)

        # Idempotency: second create should 409
        r2 = await client.post(
            "/payment/create",
            json={
                "order_no": order_no,
                "amount_cents": amount_cents,
                "currency": "USD",
            },
            headers=headers,
        )
        if r2.status_code != 409:
            print(f"WARN expected 409 on duplicate create, got {r2.status_code}")
        else:
            print("OK duplicate create blocked (409)")

        # Unsigned notify must be forbidden on stripe channel
        n = await client.post(
            "/payment/notify",
            json={
                "order_no": order_no,
                "trade_no": trade_no,
                "payload": {"type": "payment_intent.succeeded"},
            },
        )
        if n.status_code != 403:
            print(f"FAIL notify should be 403 on stripe, got {n.status_code}")
            sys.exit(1)
        print("OK unsigned /notify blocked on stripe channel")

    print("\n=== Stripe local E2E PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
