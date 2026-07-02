"""Integration tests for /api/v2/my/applicants — W41 header dropdown.

Coverage (≥ 4 cases):
  - happy: user with 3 orders (2 distinct names) → 2 entries, order_count correct
  - empty: brand-new user with no orders → items=[]
  - per-user isolation: another user's orders must NOT show up
  - malformed JSON in applicant_data is skipped silently (no 500)
  - missing surname/given_name is skipped silently
  - unauthenticated → 401
"""
from __future__ import annotations

import io
import json

import pytest

from app.core.db import AsyncSessionLocal
from app.models.destination import VisaDestination
from sqlalchemy import select, update


JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG-PAYLOAD" * 32


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, phone: str) -> str:
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


async def _upload_material(client, token: str) -> int:
    files = {"file": ("p.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
    r = await client.post(
        "/api/v2/materials/upload",
        files=files,
        data={"material_type": "passport"},
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["material"]["id"]


async def _seed_destination(code: str = "US") -> int:
    async with AsyncSessionLocal() as s:
        existing = await s.scalar(
            select(VisaDestination).where(VisaDestination.country_code == code)
        )
        if existing is not None:
            existing.enabled = True
            existing.visa_types = json.dumps(["tourism"])
            await s.commit()
            return existing.id
        dest = VisaDestination(
            country_code=code,
            country_name_i18n=json.dumps({"zh-CN": code, "en": code}, ensure_ascii=False),
            visa_types=json.dumps(["tourism"]),
            enabled=True,
            display_order=10,
        )
        s.add(dest)
        await s.commit()
        await s.refresh(dest)
        return dest.id


async def _create_order_with_applicant(
    client,
    token: str,
    dest_id: int,
    material_id: int,
    applicant: dict,
):
    """Create an order and patch its applicant_data directly in the DB.

    The POST endpoint accepts arbitrary applicant_data dict, so we can just
    send it through. Keeping this helper for parity with test_orders.
    """
    body = {
        "destination_id": dest_id,
        "visa_type": "tourism",
        "material_ids": [material_id],
        "applicant_data": applicant,
    }
    r = await client.post("/api/v2/orders", json=body, headers=_bearer(token))
    assert r.status_code == 201, r.text
    return r.json()["data"]["order_no"]


async def _force_malformed_applicant(order_no: str, raw_text: str) -> None:
    """Bypass the API to write garbage into order.applicant_data.

    We need this to verify the endpoint survives bad legacy rows.
    """
    from app.models.order import Order
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(Order).where(Order.order_no == order_no).values(applicant_data=raw_text)
        )
        await s.commit()


# ----------------------------------------------------------------- #
# Tests                                                              #
# ----------------------------------------------------------------- #
class TestMyApplicants:
    async def test_happy_dedup_and_order_count(self, client):
        """User has 3 orders: 张三 x2, 李四 x1 → 2 items, 张三 count=2."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550001")
        mid = await _upload_material(client, token)

        # Two orders for 张三 (same surname+given_name → dedup)
        await _create_order_with_applicant(
            client, token, dest_id, mid,
            {"surname": "张", "given_name": "三", "passport_no": "E11111"},
        )
        await _create_order_with_applicant(
            client, token, dest_id, mid,
            {"surname": "张", "given_name": "三", "passport_no": "E11111"},
        )
        # One order for 李四
        await _create_order_with_applicant(
            client, token, dest_id, mid,
            {"surname": "李", "given_name": "四", "passport_no": "E22222"},
        )

        r = await client.get("/api/v2/my/applicants", headers=_bearer(token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "1000"
        items = body["data"]["items"]
        assert len(items) == 2

        # Sort: newest first → 李四 (most recent created_at) before 张三
        names = [it["name"] for it in items]
        assert names == ["李四", "张三"], f"unexpected order: {names}"

        # order_count: 张三 → 2, 李四 → 1
        by_name = {it["name"]: it for it in items}
        assert by_name["张三"]["order_count"] == 2
        assert by_name["李四"]["order_count"] == 1
        assert by_name["张三"]["passport_no"] == "E11111"
        assert by_name["李四"]["passport_no"] == "E22222"

    async def test_empty_user_no_orders(self, client):
        """Brand-new user with no orders → items=[] (not 404)."""
        token = await _register(client, "13955550002")
        r = await client.get("/api/v2/my/applicants", headers=_bearer(token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "1000"
        assert body["data"]["items"] == []

    async def test_per_user_isolation(self, client):
        """User B's orders must not show up in User A's /my/applicants."""
        dest_id = await _seed_destination("US")
        token_a = await _register(client, "13955550003")
        token_b = await _register(client, "13955550004")
        mid_a = await _upload_material(client, token_a)
        mid_b = await _upload_material(client, token_b)

        await _create_order_with_applicant(
            client, token_a, dest_id, mid_a,
            {"surname": "张", "given_name": "三", "passport_no": "E11111"},
        )
        await _create_order_with_applicant(
            client, token_b, dest_id, mid_b,
            {"surname": "李", "given_name": "四", "passport_no": "E22222"},
        )

        # A sees only 张三
        r_a = await client.get("/api/v2/my/applicants", headers=_bearer(token_a))
        names_a = [it["name"] for it in r_a.json()["data"]["items"]]
        assert names_a == ["张三"], f"A leaked B's data: {names_a}"

        # B sees only 李四
        r_b = await client.get("/api/v2/my/applicants", headers=_bearer(token_b))
        names_b = [it["name"] for it in r_b.json()["data"]["items"]]
        assert names_b == ["李四"], f"B leaked A's data: {names_b}"

    async def test_malformed_json_skipped(self, client):
        """A row with garbage in applicant_data must NOT 500 the whole endpoint."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550005")
        mid = await _upload_material(client, token)

        # Good order
        good_no = await _create_order_with_applicant(
            client, token, dest_id, mid,
            {"surname": "张", "given_name": "三", "passport_no": "E11111"},
        )
        # Bad order: applicant_data is garbage
        bad_no = await _create_order_with_applicant(
            client, token, dest_id, mid,
            {"surname": "李", "given_name": "四", "passport_no": "E22222"},
        )
        await _force_malformed_applicant(bad_no, "{not valid json")

        r = await client.get("/api/v2/my/applicants", headers=_bearer(token))
        assert r.status_code == 200, r.text
        items = r.json()["data"]["items"]
        # Only 张三 from the good order; the malformed 李四 row is skipped.
        assert len(items) == 1
        assert items[0]["name"] == "张三"

    async def test_missing_required_fields_skipped(self, client):
        """applicant_data missing surname or given_name → silently skipped."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550006")
        mid = await _upload_material(client, token)

        # Missing given_name
        await _create_order_with_applicant(
            client, token, dest_id, mid,
            {"surname": "无名氏"},
        )
        # Empty surname
        await _create_order_with_applicant(
            client, token, dest_id, mid,
            {"surname": "", "given_name": "四"},
        )
        # Good
        await _create_order_with_applicant(
            client, token, dest_id, mid,
            {"surname": "张", "given_name": "三"},
        )

        r = await client.get("/api/v2/my/applicants", headers=_bearer(token))
        assert r.status_code == 200
        names = [it["name"] for it in r.json()["data"]["items"]]
        assert names == ["张三"], f"bad rows leaked through: {names}"

    async def test_unauthenticated_returns_401(self, client):
        r = await client.get("/api/v2/my/applicants")
        assert r.status_code == 401
        assert r.json()["code"] == "1005"

    async def test_western_name_has_space(self, client):
        """ASCII surname → space-separated display name."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13955550007")
        mid = await _upload_material(client, token)

        await _create_order_with_applicant(
            client, token, dest_id, mid,
            {"surname": "Smith", "given_name": "John", "passport_no": "US123456"},
        )
        r = await client.get("/api/v2/my/applicants", headers=_bearer(token))
        names = [it["name"] for it in r.json()["data"]["items"]]
        assert names == ["Smith John"]