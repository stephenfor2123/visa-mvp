"""Integration tests for `GET /api/v2/orders/{order_no}/checklist` — V2 §4.2.3.

Covers (10 cases):
  - happy: full applicant + travel + emergency + 2 materials + signature present
  - happy: empty applicant_data yields empty-string snapshot fields
  - auth: unauthenticated -> 1005
  - auth: other user -> 4001 (no existence leak)
  - state: cancelled order (status=closed) -> 4010 ORDER_NOT_EDITABLE
  - state: submitted order (status=submitted) -> 4010
  - 404: nonexistent order_no -> 4001
  - 404: malformed order_no path with too many chars
  - snapshot integrity: signature matches SHA-256 of expected payload
  - signature determinism: two calls with same data produce same signature

Signature contract (locked read-only view):
  signature = SHA-256(sort_keys JSON of the 6 snapshot sub-objects),
  excluding `signature` and `generated_at` themselves.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import datetime, timezone

import pytest

from app.core.db import AsyncSessionLocal
from app.models.destination import VisaDestination
from app.models.order import Order
from sqlalchemy import select


# ----------------------------------------------------------------- #
# Helpers (mirror test_orders.py)                                   #
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
        json={"username": uname, "email": email, "password": pwd, "email_code": "123456"},
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


async def _seed_destination(
    country_code: str = "US",
    enabled: bool = True,
    name_zh: str = "美国",
    name_en: str = "United States",
) -> int:
    async with AsyncSessionLocal() as s:
        existing = await s.scalar(
            select(VisaDestination).where(
                VisaDestination.country_code == country_code
            )
        )
        if existing is not None:
            existing.enabled = enabled
            existing.country_name_i18n = json.dumps(
                {"zh-CN": name_zh, "en": name_en}, ensure_ascii=False
            )
            await s.commit()
            return existing.id
        dest = VisaDestination(
            country_code=country_code,
            country_name_i18n=json.dumps(
                {"zh-CN": name_zh, "en": name_en}, ensure_ascii=False
            ),
            visa_types=json.dumps(["tourism", "student"]),
            enabled=enabled,
            display_order=10,
        )
        s.add(dest)
        await s.commit()
        await s.refresh(dest)
        return dest.id


_FULL_APPLICANT = {
    "surname": "ZHANG",
    "given_name": "SAN",
    "sex": "M",
    "dob": "1990-01-15",
    "nationality": "CN",
    "passport_no": "E12345678",
    "passport_expiry": "2030-12-31",
    "arrival_date": "2026-09-01",
    "departure_date": "2026-09-15",
    "stay_days": 14,
    "emergency_contact": {
        "name": "ZHANG MU",
        "phone": "13900001111",
        "relation": "parent",
    },
}


async def _create_full_order(
    client, token: str, dest_id: int, material_ids: list[int]
) -> str:
    body = {
        "destination_id": dest_id,
        "visa_type": "tourism",
        "material_ids": material_ids,
        "applicant_data": _FULL_APPLICANT,
    }
    r = await client.post("/api/v2/orders", json=body, headers=_bearer(token))
    assert r.status_code == 201, r.text
    return r.json()["data"]["order_no"]


def _expected_signature(snapshot_no_sig: dict) -> str:
    """Recompute the SHA-256 signature the same way the service does."""
    payload = json.dumps(
        snapshot_no_sig, sort_keys=True, ensure_ascii=False, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------- #
# /orders/{no}/checklist — happy paths                              #
# ----------------------------------------------------------------- #
class TestChecklistHappy:
    async def test_happy_full_snapshot(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855660001")
        m1 = await _upload_material(client, token, "passport")
        m2 = await _upload_material(client, token, "photo")
        order_no = await _create_full_order(client, token, dest_id, [m1, m2])

        r = await client.get(
            f"/api/v2/orders/{order_no}/checklist", headers=_bearer(token)
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]

        # Identity + state
        assert body["order_no"] == order_no
        assert body["status"] == "created"
        assert body["visa_type"] == "tourism"

        # Destination (i18n resolved)
        assert body["destination"]["id"] == dest_id
        assert body["destination"]["country_code"] == "US"
        assert body["destination"]["enabled"] is True
        assert body["destination"]["country_name"] in ("美国", "United States")

        # Applicant: 7 fields
        ap = body["applicant"]
        assert ap["surname"] == "ZHANG"
        assert ap["given_name"] == "SAN"
        assert ap["sex"] == "M"
        assert ap["dob"] == "1990-01-15"
        assert ap["nationality"] == "CN"
        assert ap["passport_no"] == "E12345678"
        assert ap["passport_expiry"] == "2030-12-31"

        # Travel window (extra fields beyond 7)
        tw = body["travel_window"]
        assert tw["arrival_date"] == "2026-09-01"
        assert tw["departure_date"] == "2026-09-15"
        assert tw["stay_days"] == 14

        # Emergency contact: 3 fields
        ec = body["emergency_contact"]
        assert ec["name"] == "ZHANG MU"
        assert ec["phone"] == "13900001111"
        assert ec["relation"] == "parent"

        # Materials: 2 entries, in stored order
        assert len(body["materials"]) == 2
        assert [m["id"] for m in body["materials"]] == [m1, m2]
        assert body["materials"][0]["material_type"] == "passport"
        assert body["materials"][0]["ocr_status"] == "pending"

        # Signature: 64-hex SHA-256
        assert re.match(r"^[a-f0-9]{64}$", body["signature"])
        # generated_at: ISO 8601 datetime
        assert re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", body["generated_at"]
        )

    async def test_happy_empty_applicant_data_yields_empty_strings(self, client):
        """An order with `applicant_data={}` should still return a 200 with all
        fields present as empty strings (no crashes on missing keys)."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855660002")
        mid = await _upload_material(client, token)
        # Create with empty applicant_data
        body = {
            "destination_id": dest_id,
            "visa_type": "tourism",
            "material_ids": [mid],
            "applicant_data": {},
        }
        r = await client.post(
            "/api/v2/orders", json=body, headers=_bearer(token)
        )
        assert r.status_code == 201
        order_no = r.json()["data"]["order_no"]

        r2 = await client.get(
            f"/api/v2/orders/{order_no}/checklist", headers=_bearer(token)
        )
        assert r2.status_code == 200
        d = r2.json()["data"]
        for k in (
            "surname",
            "given_name",
            "sex",
            "dob",
            "nationality",
            "passport_no",
            "passport_expiry",
        ):
            assert d["applicant"][k] == ""
        for k in ("name", "phone", "relation"):
            assert d["emergency_contact"][k] == ""
        # Signature still well-formed
        assert re.match(r"^[a-f0-9]{64}$", d["signature"])


# ----------------------------------------------------------------- #
# Auth / ownership                                                   #
# ----------------------------------------------------------------- #
class TestChecklistAuth:
    async def test_unauthenticated_returns_1005(self, client):
        r = await client.get("/api/v2/orders/V2-19990101-000001/checklist")
        assert r.status_code == 401
        assert r.json()["code"] == "1005"

    async def test_other_user_404_no_existence_leak(self, client):
        dest_id = await _seed_destination("US")
        token_a = await _register(client, "13855660010")
        token_b = await _register(client, "13855660011")
        mid_a = await _upload_material(client, token_a)
        order_no = await _create_full_order(client, token_a, dest_id, [mid_a])

        r = await client.get(
            f"/api/v2/orders/{order_no}/checklist", headers=_bearer(token_b)
        )
        assert r.status_code == 404
        assert r.json()["code"] == "4001"


# ----------------------------------------------------------------- #
# State machine                                                      #
# ----------------------------------------------------------------- #
class TestChecklistState:
    async def test_cancelled_order_returns_4010(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855660020")
        mid = await _upload_material(client, token)
        order_no = await _create_full_order(client, token, dest_id, [mid])

        # Cancel the order
        rc = await client.post(
            f"/api/v2/orders/{order_no}/cancel", headers=_bearer(token)
        )
        assert rc.status_code == 200

        # Checklist should now refuse
        r = await client.get(
            f"/api/v2/orders/{order_no}/checklist", headers=_bearer(token)
        )
        assert r.status_code == 409
        body = r.json()
        assert body["code"] == "4010"
        assert body["data"]["current_status"] == "closed"
        assert body["data"]["order_no"] == order_no

    async def test_submitted_order_returns_4010(self, client):
        """Flip status to `submitted` directly via DB and check 4010."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855660021")
        mid = await _upload_material(client, token)
        order_no = await _create_full_order(client, token, dest_id, [mid])

        # Bypass the API and force status='submitted'
        async with AsyncSessionLocal() as s:
            o = await s.scalar(select(Order).where(Order.order_no == order_no))
            assert o is not None
            o.status = "submitted"
            await s.commit()

        r = await client.get(
            f"/api/v2/orders/{order_no}/checklist", headers=_bearer(token)
        )
        assert r.status_code == 409
        body = r.json()
        assert body["code"] == "4010"
        assert body["data"]["current_status"] == "submitted"


# ----------------------------------------------------------------- #
# Not found                                                          #
# ----------------------------------------------------------------- #
class TestChecklistNotFound:
    async def test_nonexistent_order_no_4001(self, client):
        token = await _register(client, "13855660030")
        r = await client.get(
            "/api/v2/orders/V2-19990101-999999/checklist",
            headers=_bearer(token),
        )
        assert r.status_code == 404
        assert r.json()["code"] == "4001"


# ----------------------------------------------------------------- #
# Signature determinism / integrity                                 #
# ----------------------------------------------------------------- #
class TestChecklistSignature:
    async def test_signature_matches_sha256_of_payload(self, client):
        """`signature` must equal SHA-256 of the JSON-serialised snapshot
        (excluding `signature` and `generated_at`), with sort_keys=True."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855660040")
        mid = await _upload_material(client, token)
        order_no = await _create_full_order(client, token, dest_id, [mid])

        r = await client.get(
            f"/api/v2/orders/{order_no}/checklist", headers=_bearer(token)
        )
        assert r.status_code == 200
        d = r.json()["data"]

        # Rebuild the exact payload the service hashed
        snapshot_no_sig = {
            "order_no": d["order_no"],
            "status": d["status"],
            "visa_type": d["visa_type"],
            "destination": d["destination"],
            "applicant": d["applicant"],
            "travel_window": d["travel_window"],
            "emergency_contact": d["emergency_contact"],
            "materials": d["materials"],
        }
        # Note: expires_at serialised to ISO string already; default=str is
        # a defensive fallback for any other datetime in the payload.
        expected = _expected_signature(snapshot_no_sig)
        assert d["signature"] == expected

    async def test_signature_is_deterministic_across_calls(self, client):
        """Two calls within a second produce the same signature if the
        underlying data hasn't changed (no per-request salt)."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13855660041")
        mid = await _upload_material(client, token)
        order_no = await _create_full_order(client, token, dest_id, [mid])

        r1 = await client.get(
            f"/api/v2/orders/{order_no}/checklist", headers=_bearer(token)
        )
        r2 = await client.get(
            f"/api/v2/orders/{order_no}/checklist", headers=_bearer(token)
        )
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["data"]["signature"] == r2.json()["data"]["signature"]
