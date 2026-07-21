"""Integration tests for /api/v2/ds160/* (W48 v0.2).

Mirrors `backend-ds160-code-api.md` §6.2:

  1. /code idempotent when archive unchanged
  2. /code regenerates when archive field changes
  3. /code rejects non-owner with 403
  4. /code rejects order without minimum applicant_data with 422
  5. /code rejects order in terminal state with 409
  6. /redeem succeeds and returns profile
  7. /redeem rejects invalid format
  8. /redeem rejects unknown code
  9. /redeem rejects old code after archive change (the critical ARCHIVE_CHANGED path)
 10. /redeem rejects revoked code (force_rotate blacklists the old code)
 11. /redeem is rate-limited per-order after 5 attempts
 12. /portal-submitted sets ds160_portal_submitted_at (idempotent)
"""
from __future__ import annotations

import io
import json

import pytest
from sqlalchemy import select, update

from app.core.db import AsyncSessionLocal
from app.core.ds160 import get_default_rate_limiter
from app.models.destination import VisaDestination
from app.models.order import Order


JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG-PAYLOAD" * 32


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, phone: str) -> str:
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": f"u{phone}",
            "email": f"{phone}@test.local",
            "password": "Test1234",
                "email_code": "123456",
                "age_confirmed_16": True,
        },
    )
    r = await client.post(
        "/api/v2/auth/login",
        json={"account": f"{phone}@test.local", "password": "Test1234"},
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


def _full_applicant() -> dict:
    """All 5 minimum fields populated."""
    return {
        "surname": "NGUYEN",
        "given_name": "Van",
        "passport_no": "B1234567",
        "nationality": "VN",
        "birth_date": "1992-05-14",
    }


def _minimal_applicant() -> dict:
    """Missing name — should fail has_minimum_fields."""
    return {"passport_no": "B1234567"}


async def _create_order(
    client, token: str, dest_id: int, material_id: int,
    applicant: dict, visa_type: str = "tourism",
) -> str:
    r = await client.post(
        "/api/v2/orders",
        json={
            "destination_id": dest_id,
            "visa_type": visa_type,
            "material_ids": [material_id],
            "applicant_data": applicant,  # discarded until paid (A-01)
        },
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    order_no = r.json()["data"]["order_no"]
    # C-01 / A-01: DS-160 requires paid + attached applicant profile
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(Order)
            .where(Order.order_no == order_no)
            .values(
                status="paid",
                applicant_data=json.dumps(applicant, ensure_ascii=False),
            )
        )
        await s.commit()
    return order_no


async def _create_unpaid_order(
    client, token: str, dest_id: int, material_id: int,
    applicant: dict, visa_type: str = "tourism",
) -> str:
    r = await client.post(
        "/api/v2/orders",
        json={
            "destination_id": dest_id,
            "visa_type": visa_type,
            "material_ids": [material_id],
            "applicant_data": applicant,
        },
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["order_no"]


# --------------------------------------------------------------------------- #
# /code                                                                         #
# --------------------------------------------------------------------------- #

class TestIssueCode:
    async def test_reissue_rotates_code(self, client):
        """Plaintext is not stored — second /code call mints a new code."""
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000001")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())

        async with AsyncSessionLocal() as s:
            order = await s.scalar(select(Order).where(Order.order_no == order_no))
            order_id = order.id

        r1 = await client.post(
            "/api/v2/ds160/code",
            json={"order_id": order_id},
            headers=_bearer(token),
        )
        assert r1.status_code == 200, r1.text
        body1 = r1.json()["data"]
        assert body1["unchanged"] is False
        assert len(body1["code"]) == 12
        assert "expires_at" in body1

        async with AsyncSessionLocal() as s:
            order = await s.scalar(select(Order).where(Order.id == order_id))
            assert order.ds160_code is None
            assert order.ds160_code_hash and len(order.ds160_code_hash) == 64

        r2 = await client.post(
            "/api/v2/ds160/code",
            json={"order_id": order_id},
            headers=_bearer(token),
        )
        body2 = r2.json()["data"]
        assert body2["code"] != body1["code"]
        assert body2["unchanged"] is False
        assert body2["fingerprint"] == body1["fingerprint"]

    async def test_rejects_unpaid_created_order(self, client):
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000099")
        mid = await _upload_material(client, token)
        order_no = await _create_unpaid_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order = await s.scalar(select(Order).where(Order.order_no == order_no))
            order_id = order.id
            assert order.status == "created"
            assert not order.applicant_data

        r = await client.post(
            "/api/v2/ds160/code",
            json={"order_id": order_id},
            headers=_bearer(token),
        )
        assert r.status_code == 409
        assert r.json()["code"] == "11006"

    async def test_regenerates_when_field_changes(self, client):
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000002")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order = await s.scalar(select(Order).where(Order.order_no == order_no))
            order_id = order.id

        r1 = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        code1 = r1.json()["data"]["code"]

        # Mutate applicant_data directly — user editing their name in the UI
        new_data = json.dumps({**_full_applicant(), "surname": "TRAN"})
        async with AsyncSessionLocal() as s:
            await s.execute(
                update(Order).where(Order.id == order_id).values(applicant_data=new_data)
            )
            await s.commit()

        r2 = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        body2 = r2.json()["data"]
        assert body2["code"] != code1
        assert body2["unchanged"] is False

    async def test_rejects_non_owner(self, client):
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token_a = await _register(client, "13900000003")
        token_b = await _register(client, "13900000004")
        mid_a = await _upload_material(client, token_a)
        order_no = await _create_order(client, token_a, dest_id, mid_a, _full_applicant())
        async with AsyncSessionLocal() as s:
            order_id = (await s.scalar(select(Order).where(Order.order_no == order_no))).id

        r = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token_b),
        )
        assert r.status_code == 403
        assert r.json()["code"] == "1006"

    async def test_rejects_order_with_insufficient_applicant_data(self, client):
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000005")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _minimal_applicant())
        async with AsyncSessionLocal() as s:
            order_id = (await s.scalar(select(Order).where(Order.order_no == order_no))).id

        r = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        assert r.status_code == 422
        assert r.json()["code"] == "11005"

    async def test_rejects_terminal_order(self, client):
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000006")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order = await s.scalar(select(Order).where(Order.order_no == order_no))
            order.status = "closed"
            await s.commit()
            order_id = order.id

        r = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        assert r.status_code == 409
        assert r.json()["code"] == "11006"

    async def test_force_rotate_invalidates_old_code(self, client):
        """force_rotate issues a new code AND invalidates the old one.

        The previously-active code is pushed onto a per-order `revoked_codes`
        JSON list; /redeem rejects it with 11002 CODE_REVOKED before the
        fingerprint check, so the user's old browser tab gets a clear,
        actionable error.
        """
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000007")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order_id = (await s.scalar(select(Order).where(Order.order_no == order_no))).id

        r1 = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        code1 = r1.json()["data"]["code"]

        r2 = await client.post(
            "/api/v2/ds160/code",
            json={"order_id": order_id, "force_rotate": True},
            headers=_bearer(token),
        )
        code2 = r2.json()["data"]["code"]
        assert code1 != code2
        assert r2.json()["data"]["unchanged"] is False

        # Old code is now in revoked_codes list → 11002 CODE_REVOKED
        r_redeem = await client.post(
            "/api/v2/ds160/code/redeem", json={"code": code1},
        )
        assert r_redeem.status_code == 409
        assert r_redeem.json()["code"] == "11002"


# --------------------------------------------------------------------------- #
# /redeem                                                                       #
# --------------------------------------------------------------------------- #

class TestRedeemCode:
    async def test_happy_path(self, client):
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000008")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order_id = (await s.scalar(select(Order).where(Order.order_no == order_no))).id

        r_issue = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        code = r_issue.json()["data"]["code"]

        r_redeem = await client.post(
            "/api/v2/ds160/code/redeem", json={"code": code},
        )
        assert r_redeem.status_code == 200, r_redeem.text
        body = r_redeem.json()["data"]
        assert body["order_id"] == order_id
        assert body["profile"]["identity"]["surname"] == "NGUYEN"
        assert body["profile"]["identity"]["givenName"] == "Van"
        assert body["profile"]["passport"]["number"] == "B1234567"
        assert len(body["fingerprint"]) == 32

        # E-03: single-use — second redeem fails
        r2 = await client.post(
            "/api/v2/ds160/code/redeem", json={"code": code},
        )
        assert r2.status_code == 409
        assert r2.json()["code"] in ("11008", "11002")

    async def test_rejects_invalid_format(self, client):
        get_default_rate_limiter().reset()
        # Pydantic min_length=12 catches "too-short" before our format check;
        # we exercise the format check with strings of valid length but bad chars.
        # Has confusable chars (0/O/1/I/L/U)
        r = await client.post(
            "/api/v2/ds160/code/redeem", json={"code": "ABC0EFGHIJKL"},
        )
        assert r.status_code == 400
        assert r.json()["code"] == "11004"

        r2 = await client.post(
            "/api/v2/ds160/code/redeem", json={"code": "ILOUABCDEFGH"},
        )
        assert r2.status_code == 400
        assert r2.json()["code"] == "11004"

    async def test_rejects_unknown_code(self, client):
        get_default_rate_limiter().reset()
        r = await client.post(
            "/api/v2/ds160/code/redeem",
            json={"code": "ABCDEFGHJKLM"},  # valid format, never issued
        )
        assert r.status_code == 404
        assert r.json()["code"] == "11001"

    async def test_archive_changed_returns_409(self, client):
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000009")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order_id = (await s.scalar(select(Order).where(Order.order_no == order_no))).id

        r_issue = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        code = r_issue.json()["data"]["code"]

        # Simulate the user editing their surname AFTER the code was issued
        new_data = json.dumps({**_full_applicant(), "surname": "TRAN"})
        async with AsyncSessionLocal() as s:
            await s.execute(
                update(Order).where(Order.id == order_id).values(applicant_data=new_data)
            )
            await s.commit()

        r = await client.post(
            "/api/v2/ds160/code/redeem", json={"code": code},
        )
        assert r.status_code == 409
        body = r.json()
        assert body["code"] == "11003"
        # The hint data should include fingerprint prefixes so the client can
        # show "档案已更新, 请回 Htex 拿新 code" with proof.
        assert "hint" in body["data"]
        assert body["data"]["issued_fingerprint_prefix"]
        assert body["data"]["current_fingerprint_prefix"]

    async def test_rate_limited_per_order(self, client):
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000010")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order_id = (await s.scalar(select(Order).where(Order.order_no == order_no))).id

        r_issue = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        code = r_issue.json()["data"]["code"]

        # 1st redeem succeeds (single-use); next 4 return USED; 6th is rate-limited
        r1 = await client.post("/api/v2/ds160/code/redeem", json={"code": code})
        assert r1.status_code == 200, r1.text
        for _ in range(4):
            r = await client.post("/api/v2/ds160/code/redeem", json={"code": code})
            assert r.status_code == 409
        r6 = await client.post("/api/v2/ds160/code/redeem", json={"code": code})
        assert r6.status_code == 429
        assert r6.json()["code"] == "1009"

    async def test_no_session_required(self, client):
        """The /redeem endpoint MUST work without Authorization header."""
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000011")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order_id = (await s.scalar(select(Order).where(Order.order_no == order_no))).id

        r_issue = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        code = r_issue.json()["data"]["code"]

        # No Authorization header — code is the credential
        r = await client.post(
            "/api/v2/ds160/code/redeem", json={"code": code},
        )
        assert r.status_code == 200, r.text

    async def test_audit_log_written(self, client):
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000012")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order_id = (await s.scalar(select(Order).where(Order.order_no == order_no))).id

        r_issue = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        code = r_issue.json()["data"]["code"]

        await client.post("/api/v2/ds160/code/redeem", json={"code": code})

        # Both issue + redeem events should be in audit_log
        from app.models.audit_log import AuditLog
        async with AsyncSessionLocal() as s:
            logs = (await s.execute(
                select(AuditLog).where(
                    AuditLog.target_id == order_id,
                    AuditLog.action == "ds160.code.redeem",
                )
            )).scalars().all()
        assert len(logs) == 1
        payload = json.loads(logs[0].payload)
        assert payload["success"] is True
        assert payload["fingerprint_prefix"]


# --------------------------------------------------------------------------- #
# /portal-submitted                                                           #
# --------------------------------------------------------------------------- #

class TestPortalSubmitted:
    async def test_happy_path_and_idempotent(self, client):
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000020")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order_id = (await s.scalar(select(Order).where(Order.order_no == order_no))).id

        r_issue = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        code = r_issue.json()["data"]["code"]

        r1 = await client.post(
            "/api/v2/ds160/portal-submitted", json={"code": code},
        )
        assert r1.status_code == 200, r1.text
        body1 = r1.json()["data"]
        assert body1["order_id"] == order_id
        assert body1["unchanged"] is False
        assert body1["ds160_portal_submitted_at"]

        async with AsyncSessionLocal() as s:
            order = await s.scalar(select(Order).where(Order.id == order_id))
            assert order.ds160_portal_submitted_at is not None

        r2 = await client.post(
            "/api/v2/ds160/portal-submitted", json={"code": code},
        )
        assert r2.status_code == 200
        body2 = r2.json()["data"]
        assert body2["unchanged"] is True
        assert body2["ds160_portal_submitted_at"] == body1["ds160_portal_submitted_at"]

    async def test_rejects_revoked_code(self, client):
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000021")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order_id = (await s.scalar(select(Order).where(Order.order_no == order_no))).id

        r1 = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        code1 = r1.json()["data"]["code"]

        await client.post(
            "/api/v2/ds160/code",
            json={"order_id": order_id, "force_rotate": True},
            headers=_bearer(token),
        )

        r = await client.post(
            "/api/v2/ds160/portal-submitted", json={"code": code1},
        )
        assert r.status_code == 409
        assert r.json()["code"] == "11002"

    async def test_no_fingerprint_check(self, client):
        """Portal-submitted does NOT require archive fingerprint match (unlike /redeem)."""
        get_default_rate_limiter().reset()
        dest_id = await _seed_destination()
        token = await _register(client, "13900000022")
        mid = await _upload_material(client, token)
        order_no = await _create_order(client, token, dest_id, mid, _full_applicant())
        async with AsyncSessionLocal() as s:
            order_id = (await s.scalar(select(Order).where(Order.order_no == order_no))).id

        r_issue = await client.post(
            "/api/v2/ds160/code", json={"order_id": order_id}, headers=_bearer(token),
        )
        code = r_issue.json()["data"]["code"]

        new_data = json.dumps({**_full_applicant(), "surname": "TRAN"})
        async with AsyncSessionLocal() as s:
            await s.execute(
                update(Order).where(Order.id == order_id).values(applicant_data=new_data)
            )
            await s.commit()

        r_redeem = await client.post(
            "/api/v2/ds160/code/redeem", json={"code": code},
        )
        assert r_redeem.status_code == 409  # ARCHIVE_CHANGED

        r_portal = await client.post(
            "/api/v2/ds160/portal-submitted", json={"code": code},
        )
        assert r_portal.status_code == 200, r_portal.text
        assert r_portal.json()["data"]["unchanged"] is False