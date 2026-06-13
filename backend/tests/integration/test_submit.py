"""Integration tests for `POST /api/v2/orders/{order_no}/submit` — V2 §4.2.4.

Story 1.2.2b — order submit endpoint.

Covers (7 cases):
  - happy: status=created + matching signature → 200, status=submitted,
    submitted_at + rpa_task_id populated, OrderStatusHistory row written
  - signature mismatch: 4011 ORDER_SIGNATURE_MISMATCH
  - already submitted: 4010 ORDER_NOT_EDITABLE (status=submitted)
  - status=reviewing: 4010 (re-checks after build_checklist's gate)
  - not owned: another user → 4001 (no existence leak)
  - nonexistent order: 4001
  - history row + audit row written on success
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone

import pytest

from app.core.db import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.destination import VisaDestination
from app.models.order import Order, OrderStatusHistory
from sqlalchemy import select


# ----------------------------------------------------------------- #
# Helpers (mirror test_checklist.py / test_orders.py)               #
# ----------------------------------------------------------------- #
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG-PAYLOAD" * 32


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, phone: str) -> str:
    r = await client.post(
        "/api/v2/auth/sms-login",
        json={"phone": phone, "phone_country": "+86", "sms_code": "123456"},
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
    import json
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
    "surname": "LI",
    "given_name": "SI",
    "sex": "F",
    "dob": "1992-05-20",
    "nationality": "CN",
    "passport_no": "E98765432",
    "passport_expiry": "2031-06-30",
    "arrival_date": "2026-10-01",
    "departure_date": "2026-10-15",
    "stay_days": 14,
    "emergency_contact": {
        "name": "LI MU",
        "phone": "13900002222",
        "relation": "spouse",
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


async def _get_checklist_signature(
    client, token: str, order_no: str
) -> tuple[str, str]:
    """Call GET /checklist and return (signature, generated_at)."""
    r = await client.get(
        f"/api/v2/orders/{order_no}/checklist", headers=_bearer(token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    return d["signature"], d["generated_at"]


# ----------------------------------------------------------------- #
# /orders/{no}/submit — happy path                                  #
# ----------------------------------------------------------------- #
class TestSubmitHappy:
    async def test_submit_happy_path(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13866660001")
        m1 = await _upload_material(client, token, "passport")
        m2 = await _upload_material(client, token, "photo")
        order_no = await _create_full_order(client, token, dest_id, [m1, m2])

        sig, _ = await _get_checklist_signature(client, token, order_no)

        r = await client.post(
            f"/api/v2/orders/{order_no}/submit",
            json={"signature": sig},
            headers=_bearer(token),
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["order_no"] == order_no
        assert body["status"] == "submitted"
        # submitted_at is ISO 8601 and within a sane window (last 10s)
        assert re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", body["submitted_at"]
        )
        submitted_at = datetime.fromisoformat(body["submitted_at"])
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        assert abs((now - submitted_at).total_seconds()) < 10
        # rpa_task_id is a UUID4 string
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            body["rpa_task_id"],
        ), f"bad rpa_task_id: {body['rpa_task_id']}"

        # GET /orders/{no} now shows status=submitted and 2 history rows
        r2 = await client.get(
            f"/api/v2/orders/{order_no}", headers=_bearer(token)
        )
        assert r2.status_code == 200
        d = r2.json()["data"]
        assert d["status"] == "submitted"
        assert d["rpa_task_id"] == body["rpa_task_id"]
        hist = d["status_history"]
        assert len(hist) == 2
        # Most recent (last) is created → submitted
        assert hist[0]["to_status"] == "created"
        assert hist[1]["from_status"] == "created"
        assert hist[1]["to_status"] == "submitted"
        assert hist[1]["source"] == "user"


# ----------------------------------------------------------------- #
# Signature mismatch                                                #
# ----------------------------------------------------------------- #
class TestSubmitSignatureMismatch:
    async def test_signature_mismatch_returns_4011(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13866660010")
        mid = await _upload_material(client, token)
        order_no = await _create_full_order(client, token, dest_id, [mid])

        # Don't call /checklist at all — fabricate a wrong-but-valid-format sig
        wrong_sig = "0" * 64

        r = await client.post(
            f"/api/v2/orders/{order_no}/submit",
            json={"signature": wrong_sig},
            headers=_bearer(token),
        )
        assert r.status_code == 400, r.text
        body = r.json()
        assert body["code"] == "4011"
        assert body["data"]["order_no"] == order_no
        # Server exposes 12-char prefix of the expected signature for debug
        assert re.match(r"^[a-f0-9]{12}$", body["data"]["expected_signature_prefix"])

        # Order should still be `created` (submit was rejected)
        r2 = await client.get(
            f"/api/v2/orders/{order_no}", headers=_bearer(token)
        )
        assert r2.status_code == 200
        assert r2.json()["data"]["status"] == "created"

    async def test_signature_malformed_returns_1001(self, client):
        """Non-hex or wrong length signature is rejected at the Pydantic
        layer with 1001 INVALID_PARAMS (400)."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13866660011")
        mid = await _upload_material(client, token)
        order_no = await _create_full_order(client, token, dest_id, [mid])

        # 63 chars (too short)
        r = await client.post(
            f"/api/v2/orders/{order_no}/submit",
            json={"signature": "a" * 63},
            headers=_bearer(token),
        )
        assert r.status_code == 400
        assert r.json()["code"] == "1001"

        # Non-hex (64 chars but with 'z')
        r2 = await client.post(
            f"/api/v2/orders/{order_no}/submit",
            json={"signature": "z" * 64},
            headers=_bearer(token),
        )
        assert r2.status_code == 400
        assert r2.json()["code"] == "1001"


# ----------------------------------------------------------------- #
# State machine — only `created` is submittable                     #
# ----------------------------------------------------------------- #
class TestSubmitState:
    async def test_already_submitted_returns_4010(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13866660020")
        mid = await _upload_material(client, token)
        order_no = await _create_full_order(client, token, dest_id, [mid])

        sig, _ = await _get_checklist_signature(client, token, order_no)

        # First submit → 200
        r1 = await client.post(
            f"/api/v2/orders/{order_no}/submit",
            json={"signature": sig},
            headers=_bearer(token),
        )
        assert r1.status_code == 200

        # Second submit with the same (now stale) signature → 4010
        r2 = await client.post(
            f"/api/v2/orders/{order_no}/submit",
            json={"signature": sig},
            headers=_bearer(token),
        )
        assert r2.status_code == 409
        body = r2.json()
        assert body["code"] == "4010"
        assert body["data"]["current_status"] == "submitted"

    async def test_status_reviewing_returns_4010(self, client):
        """Force status='reviewing' (skipping the API) and verify 4010."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13866660021")
        mid = await _upload_material(client, token)
        order_no = await _create_full_order(client, token, dest_id, [mid])

        # Bypass API
        async with AsyncSessionLocal() as s:
            o = await s.scalar(select(Order).where(Order.order_no == order_no))
            assert o is not None
            o.status = "reviewing"
            await s.commit()

        # Build a fake signature of the right shape (server will still
        # gate on status before the signature check fires)
        r = await client.post(
            f"/api/v2/orders/{order_no}/submit",
            json={"signature": "a" * 64},
            headers=_bearer(token),
        )
        assert r.status_code == 409
        body = r.json()
        assert body["code"] == "4010"
        assert body["data"]["current_status"] == "reviewing"

    async def test_cancelled_order_returns_4010(self, client):
        dest_id = await _seed_destination("US")
        token = await _register(client, "13866660022")
        mid = await _upload_material(client, token)
        order_no = await _create_full_order(client, token, dest_id, [mid])

        rc = await client.post(
            f"/api/v2/orders/{order_no}/cancel", headers=_bearer(token)
        )
        assert rc.status_code == 200

        r = await client.post(
            f"/api/v2/orders/{order_no}/submit",
            json={"signature": "a" * 64},
            headers=_bearer(token),
        )
        assert r.status_code == 409
        body = r.json()
        assert body["code"] == "4010"
        assert body["data"]["current_status"] == "closed"


# ----------------------------------------------------------------- #
# Auth / ownership                                                   #
# ----------------------------------------------------------------- #
class TestSubmitAuth:
    async def test_unauthenticated_returns_1005(self, client):
        r = await client.post(
            "/api/v2/orders/V2-19990101-000001/submit",
            json={"signature": "a" * 64},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "1005"

    async def test_not_owned_returns_4001(self, client):
        dest_id = await _seed_destination("US")
        token_a = await _register(client, "13866660030")
        token_b = await _register(client, "13866660031")
        mid_a = await _upload_material(client, token_a)
        order_no = await _create_full_order(client, token_a, dest_id, [mid_a])

        # B's submit with even a valid-format sig is rejected
        r = await client.post(
            f"/api/v2/orders/{order_no}/submit",
            json={"signature": "a" * 64},
            headers=_bearer(token_b),
        )
        assert r.status_code == 404
        assert r.json()["code"] == "4001"

    async def test_nonexistent_order_returns_4001(self, client):
        token = await _register(client, "13866660032")
        r = await client.post(
            "/api/v2/orders/V2-19990101-999999/submit",
            json={"signature": "a" * 64},
            headers=_bearer(token),
        )
        assert r.status_code == 404
        assert r.json()["code"] == "4001"


# ----------------------------------------------------------------- #
# Side effects — history + audit row                                #
# ----------------------------------------------------------------- #
class TestSubmitSideEffects:
    async def test_history_and_audit_rows_written(self, client):
        """Submit must append exactly one OrderStatusHistory row (created →
        submitted) and one AuditLog row (action='order.submit')."""
        dest_id = await _seed_destination("US")
        token = await _register(client, "13866660040")
        mid = await _upload_material(client, token)
        order_no = await _create_full_order(client, token, dest_id, [mid])

        sig, _ = await _get_checklist_signature(client, token, order_no)

        r = await client.post(
            f"/api/v2/orders/{order_no}/submit",
            json={"signature": sig},
            headers=_bearer(token),
        )
        assert r.status_code == 200, r.text

        async with AsyncSessionLocal() as s:
            o = await s.scalar(select(Order).where(Order.order_no == order_no))
            assert o is not None
            order_id = o.id

            # History: 2 rows total (created + submitted)
            hist_rows = (
                await s.execute(
                    select(OrderStatusHistory)
                    .where(OrderStatusHistory.order_id == order_id)
                    .order_by(OrderStatusHistory.created_at)
                )
            ).scalars().all()
            assert len(hist_rows) == 2
            assert hist_rows[0].from_status is None
            assert hist_rows[0].to_status == "created"
            assert hist_rows[1].from_status == "created"
            assert hist_rows[1].to_status == "submitted"
            assert hist_rows[1].source == "user"
            assert hist_rows[1].note == "order submitted to RPA"

            # Audit: at least one order.submit row
            audit_rows = (
                await s.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.target_id == order_id,
                        AuditLog.action == "order.submit",
                    )
                )
            ).scalars().all()
            assert len(audit_rows) == 1
            import json as _json
            payload = _json.loads(audit_rows[0].payload or "{}")
            assert payload["order_no"] == order_no
            assert payload["from_status"] == "created"
            assert payload["rpa_task_id"] == r.json()["data"]["rpa_task_id"]
