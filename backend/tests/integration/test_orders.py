"""Integration tests for /api/v2/orders/* — V2 §4.2 Order Service.

Covers (≥ 6 cases, 10 here):
  - create:  happy / unauth / bad-visa-type / missing-destination / no-materials /
             material-not-owned / disabled-destination
  - list:    paginated / status-filter / per-user isolation
  - detail:  happy-with-history / 404 / 403-other-user
  - cancel:  happy / 409-already-closed

Order number generator is exercised via creating multiple orders in a single
day and asserting the V2-YYYYMMDD-NNNNNN shape + monotonic sequence.
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone

import pytest

from app.core.db import AsyncSessionLocal
from app.models.destination import VisaDestination
from sqlalchemy import select


# ----------------------------------------------------------------- #
# Helpers                                                            #
# ----------------------------------------------------------------- #
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG-PAYLOAD" * 32


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, phone: str) -> str:
    """Register or reuse account keyed by phone → returns access token."""
    uname = f"u{phone}"
    email = f"{phone}@test.local"
    pwd = "Test1234"
    await client.post(
        "/api/v2/auth/register",
        json={"username": uname, "email": email, "password": pwd},
    )
    r = await client.post(
        "/api/v2/auth/login",
        json={"account": email, "password": pwd},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _upload_material(client, token: str, mat_type: str = "passport") -> int:
    """Upload one material via the real endpoint and return its id."""
    files = {"file": (f"{mat_type}.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
    r = await client.post(
        "/api/v2/materials/upload",
        files=files,
        data={"material_type": mat_type},
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["material"]["id"]


async def _seed_destination(
    country_code: str = "US",
    enabled: bool = True,
    visa_types: list[str] | None = None,
) -> int:
    """Insert a VisaDestination row directly via the test DB session."""
    import json
    visa_types = visa_types or ["tourism", "student"]
    async with AsyncSessionLocal() as s:
        existing = await s.scalar(
            select(VisaDestination).where(
                VisaDestination.country_code == country_code
            )
        )
        if existing is not None:
            # Refresh `enabled` so tests can flip it without leaving residue
            existing.enabled = enabled
            existing.visa_types = json.dumps(visa_types)
            await s.commit()
            return existing.id
        dest = VisaDestination(
            country_code=country_code,
            country_name_i18n=json.dumps(
                {"zh-CN": country_code, "en": country_code}, ensure_ascii=False
            ),
            visa_types=json.dumps(visa_types),
            enabled=enabled,
            display_order=10,
        )
        s.add(dest)
        await s.commit()
        await s.refresh(dest)
        return dest.id


async def _seed_destination_disabled() -> int:
    return await _seed_destination("ZZ", enabled=False)


async def _create_order(
    client,
    token: str,
    dest_id: int,
    material_ids: list[int],
    visa_type: str = "tourism",
    applicant_data: dict | None = None,
):
    body = {
        "destination_id": dest_id,
        "visa_type": visa_type,
        "material_ids": material_ids,
        "applicant_data": applicant_data or {"name": "Alice"},
    }
    return await client.post("/api/v2/orders", json=body, headers=_bearer(token))


# ----------------------------------------------------------------- #
# /orders POST                                                        #
# ----------------------------------------------------------------- #
class TestCreateOrder:
    async def test_happy_201_returns_order_no(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855550001")
        mid = await _upload_material(client, token)
        r = await _create_order(client, token, dest_id, [mid])
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["code"] == "1000"
        order_no = body["data"]["order_no"]
        assert re.match(r"^V2-\d{8}-[0-9A-F]{8}$", order_no), f"bad order_no: {order_no}"
        assert body["data"]["status"] == "created"
        assert body["data"]["order"]["user_id"] > 0
        assert body["data"]["order"]["visa_type"] == "tourism"
        assert body["data"]["order"]["material_ids"] == [mid]
        assert body["data"]["order"]["applicant_data"]["name"] == "Alice"

    async def test_unauthenticated_returns_1005(self, client):
        r = await client.post(
            "/api/v2/orders",
            json={
                "destination_id": 1,
                "visa_type": "tourism",
                "material_ids": [1],
            },
        )
        assert r.status_code == 401
        assert r.json()["code"] == "1005"

    async def test_invalid_visa_type_1001(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855550002")
        mid = await _upload_material(client, token)
        r = await _create_order(
            client, token, dest_id, [mid], visa_type="diplomatic_immunity"
        )
        assert r.status_code == 400
        assert r.json()["code"] == "1001"

    async def test_missing_destination_4004(self, client):
        token = await _register(client, "13855550003")
        mid = await _upload_material(client, token)
        r = await _create_order(client, token, 99999, [mid])
        assert r.status_code == 400
        assert r.json()["code"] == "4004"

    async def test_disabled_destination_4004(self, client):
        dest_id = await _seed_destination_disabled()
        token = await _register(client, "13855550004")
        mid = await _upload_material(client, token)
        r = await _create_order(client, token, dest_id, [mid])
        assert r.status_code == 400
        assert r.json()["code"] == "4004"
        assert r.json()["data"]["country_code"] == "ZZ"

    async def test_material_not_owned_4006(self, client):
        dest_id = await _seed_destination("US")
        token_a = await _register(client, "13855550005")
        token_b = await _register(client, "13855550006")
        mid_a = await _upload_material(client, token_a)
        # B tries to use A's material
        r = await _create_order(client, token_b, dest_id, [mid_a])
        assert r.status_code == 403
        assert r.json()["code"] == "4006"

    async def test_missing_materials_1001(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855550007")
        # empty material_ids
        r = await client.post(
            "/api/v2/orders",
            json={"destination_id": dest_id, "visa_type": "tourism", "material_ids": []},
            headers=_bearer(token),
        )
        assert r.status_code == 400
        assert r.json()["code"] == "1001"

    async def test_nonexistent_material_4005(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855550008")
        r = await _create_order(client, token, dest_id, [99999])
        assert r.status_code == 400
        assert r.json()["code"] == "4005"


# ----------------------------------------------------------------- #
# /orders GET — list                                                  #
# ----------------------------------------------------------------- #
class TestListOrders:
    async def test_happy_paginated(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855550010")
        mid = await _upload_material(client, token)
        for _ in range(3):
            r = await _create_order(client, token, dest_id, [mid])
            assert r.status_code == 201

        r = await client.get("/api/v2/orders?page=1&page_size=2", headers=_bearer(token))
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["page_size"] == 2
        assert body["total_pages"] == 2
        assert len(body["items"]) == 2
        # items are ordered by created_at DESC -> first is the newest
        first = body["items"][0]
        assert re.match(r"^V2-\d{8}-[0-9A-F]{8}$", first["order_no"])
        assert first["status"] == "created"

        r2 = await client.get(
            "/api/v2/orders?page=2&page_size=2", headers=_bearer(token)
        )
        assert r2.status_code == 200
        assert len(r2.json()["data"]["items"]) == 1

    async def test_status_filter(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855550011")
        mid = await _upload_material(client, token)
        r1 = await _create_order(client, token, dest_id, [mid])
        no1 = r1.json()["data"]["order_no"]
        r2 = await _create_order(client, token, dest_id, [mid])
        no2 = r2.json()["data"]["order_no"]
        # Cancel one
        await client.post(f"/api/v2/orders/{no1}/cancel", headers=_bearer(token))

        r = await client.get(
            "/api/v2/orders?status=created", headers=_bearer(token)
        )
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["total"] == 1
        assert body["items"][0]["order_no"] == no2

        r = await client.get(
            "/api/v2/orders?status=closed", headers=_bearer(token)
        )
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["total"] == 1
        assert body["items"][0]["order_no"] == no1

    async def test_per_user_isolation(self, client):
        dest_id = await _seed_destination("US")
        token_a = await _register(client, "13855550012")
        token_b = await _register(client, "13855550013")
        mid_a = await _upload_material(client, token_a)
        mid_b = await _upload_material(client, token_b)
        await _create_order(client, token_a, dest_id, [mid_a])
        await _create_order(client, token_b, dest_id, [mid_b])

        r_a = await client.get("/api/v2/orders", headers=_bearer(token_a))
        r_b = await client.get("/api/v2/orders", headers=_bearer(token_b))
        assert r_a.json()["data"]["total"] == 1
        assert r_b.json()["data"]["total"] == 1
        assert r_a.json()["data"]["items"][0]["user_id"] != r_b.json()["data"]["items"][0]["user_id"]


# ----------------------------------------------------------------- #
# /orders/{order_no}                                                  #
# ----------------------------------------------------------------- #
class TestGetOrderDetail:
    async def test_happy_includes_history_and_materials(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855550020")
        mid1 = await _upload_material(client, token, "passport")
        mid2 = await _upload_material(client, token, "photo")
        r = await _create_order(
            client, token, dest_id, [mid1, mid2],
            applicant_data={"name": "Alice", "passport_no": "X1234567"},
        )
        order_no = r.json()["data"]["order_no"]

        r2 = await client.get(
            f"/api/v2/orders/{order_no}", headers=_bearer(token)
        )
        assert r2.status_code == 200, r2.text
        body = r2.json()["data"]
        assert body["order_no"] == order_no
        assert body["status"] == "created"
        assert body["applicant_data"]["name"] == "Alice"
        # status_history
        assert len(body["status_history"]) == 1
        h0 = body["status_history"][0]
        assert h0["from_status"] is None
        assert h0["to_status"] == "created"
        assert h0["source"] == "user"
        # material refs (no order_id filtering on result, just that the IDs match)
        mat_ids = {m["id"] for m in body["materials"]}
        assert {mid1, mid2} == mat_ids

    async def test_not_found_4001(self, client):
        token = await _register(client, "13855550021")
        r = await client.get(
            "/api/v2/orders/V2-19990101-000001", headers=_bearer(token)
        )
        assert r.status_code == 404
        assert r.json()["code"] == "4001"

    async def test_other_user_404(self, client):
        dest_id = await _seed_destination("US")
        token_a = await _register(client, "13855550022")
        token_b = await _register(client, "13855550023")
        mid_a = await _upload_material(client, token_a)
        r = await _create_order(client, token_a, dest_id, [mid_a])
        order_no = r.json()["data"]["order_no"]

        r2 = await client.get(
            f"/api/v2/orders/{order_no}", headers=_bearer(token_b)
        )
        assert r2.status_code == 404
        assert r2.json()["code"] == "4001"


# ----------------------------------------------------------------- #
# /orders/{order_no}/cancel                                           #
# ----------------------------------------------------------------- #
class TestCancelOrder:
    async def test_happy_created_to_closed(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855550030")
        mid = await _upload_material(client, token)
        r = await _create_order(client, token, dest_id, [mid])
        order_no = r.json()["data"]["order_no"]

        rc = await client.post(
            f"/api/v2/orders/{order_no}/cancel", headers=_bearer(token)
        )
        assert rc.status_code == 200, rc.text
        body = rc.json()["data"]
        assert body["order_no"] == order_no
        assert body["status"] == "closed"

        # detail now shows 2 history rows
        rd = await client.get(
            f"/api/v2/orders/{order_no}", headers=_bearer(token)
        )
        hist = rd.json()["data"]["status_history"]
        assert len(hist) == 2
        assert hist[0]["to_status"] == "created"
        assert hist[1]["from_status"] == "created"
        assert hist[1]["to_status"] == "closed"
        assert hist[1]["source"] == "user"

    async def test_cancel_twice_409(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855550031")
        mid = await _upload_material(client, token)
        r = await _create_order(client, token, dest_id, [mid])
        order_no = r.json()["data"]["order_no"]

        rc1 = await client.post(
            f"/api/v2/orders/{order_no}/cancel", headers=_bearer(token)
        )
        assert rc1.status_code == 200

        rc2 = await client.post(
            f"/api/v2/orders/{order_no}/cancel", headers=_bearer(token)
        )
        assert rc2.status_code == 409
        # W3-3 enforcement: cancel endpoint now uses 4010 ORDER_NOT_EDITABLE
        # (shared with checklist/submit state-gate). Message must contain
        # endpoint keyword "cancel" so E2E (qa/E2E/orderdetail.spec.js case 3)
        # and i18n fallbacks can disambiguate.
        assert rc2.json()["code"] == "4010"
        assert "cancel" in rc2.json()["message"]

    async def test_cancel_not_owned_404(self, client):
        dest_id = await _seed_destination("US")
        token_a = await _register(client, "13855550032")
        token_b = await _register(client, "13855550033")
        mid_a = await _upload_material(client, token_a)
        r = await _create_order(client, token_a, dest_id, [mid_a])
        order_no = r.json()["data"]["order_no"]

        rc = await client.post(
            f"/api/v2/orders/{order_no}/cancel", headers=_bearer(token_b)
        )
        assert rc.status_code == 404
        assert rc.json()["code"] == "4001"


# ----------------------------------------------------------------- #
# Order number generator                                              #
# ----------------------------------------------------------------- #
class TestOrderNumberGenerator:
    async def test_three_orders_in_a_day_have_unique_nos(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855550040")
        mid = await _upload_material(client, token)
        numbers: list[str] = []
        for _ in range(3):
            r = await _create_order(client, token, dest_id, [mid])
            assert r.status_code == 201
            numbers.append(r.json()["data"]["order_no"])
        # All share today's prefix
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        prefix = f"V2-{today}-"
        for n in numbers:
            assert n.startswith(prefix), f"unexpected prefix: {n}"
        # All three are unique (hex UUID suffix — not sequential by design)
        assert len(set(numbers)) == 3

    async def test_format_well_formed(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855550041")
        mid = await _upload_material(client, token)
        r = await _create_order(client, token, dest_id, [mid])
        order_no = r.json()["data"]["order_no"]
        # Format: V2-YYYYMMDD-XXXXXXXX (8 uppercase hex chars)
        match = re.match(r"^V2-(\d{4})(\d{2})(\d{2})-([0-9A-F]{8})$", order_no)
        assert match, f"bad order_no: {order_no}"
        y, m, d, _hex = match.groups()
        # Today's date in UTC
        now = datetime.now(timezone.utc)
        assert int(y) == now.year
        assert int(m) == now.month
        assert int(d) == now.day
