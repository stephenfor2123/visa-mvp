"""Public destinations list must respect admin country toggles."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.destination import VisaDestination
from app.models.visa_countries import VisaCountry


async def _ensure_destination(code: str = "US", *, enabled: bool = True) -> VisaDestination:
    async with AsyncSessionLocal() as s:
        row = await s.scalar(
            select(VisaDestination).where(VisaDestination.country_code == code)
        )
        if row is None:
            row = VisaDestination(
                country_code=code,
                country_name_i18n=json.dumps({"zh-CN": "美国", "en": "United States"}),
                visa_types=json.dumps(["tourism"]),
                enabled=enabled,
                display_order=1,
            )
            s.add(row)
        else:
            row.enabled = enabled
        await s.commit()
        await s.refresh(row)
        return row


async def _ensure_country(code: str = "US", *, enabled: bool = True) -> VisaCountry:
    async with AsyncSessionLocal() as s:
        row = await s.scalar(
            select(VisaCountry).where(VisaCountry.country_code == code)
        )
        if row is None:
            row = VisaCountry(
                country_code=code,
                country_name_zh="美国",
                country_name_en="United States",
                enabled=enabled,
                display_order=1,
                visa_types=json.dumps(["tourism"]),
            )
            s.add(row)
        else:
            row.enabled = enabled
        await s.commit()
        await s.refresh(row)
        return row


async def _admin_token(client) -> str:
    r = await client.post(
        "/api/v2/admin/login",
        json={"username": "admin", "password": "visa-admin-2024"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


@pytest.mark.asyncio
class TestDestinationAdminToggle:
    async def test_disabled_admin_country_hidden_from_public_list(self, client):
        await _ensure_destination("US", enabled=True)
        await _ensure_country("US", enabled=False)

        r = await client.get("/api/v2/destinations")
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == "1000"
        codes = {d["country_code"] for d in body["data"]}
        assert "US" not in codes

    async def test_enabled_admin_country_visible_on_public_list(self, client):
        await _ensure_destination("US", enabled=True)
        await _ensure_country("US", enabled=True)

        r = await client.get("/api/v2/destinations")
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == "1000"
        codes = {d["country_code"] for d in body["data"]}
        assert "US" in codes

    async def test_toggle_syncs_destination_and_hides_public(self, client):
        dest = await _ensure_destination("US", enabled=True)
        country = await _ensure_country("US", enabled=True)
        token = await _admin_token(client)

        r = await client.post(
            f"/api/v2/admin/config/countries/{country.id}/toggle",
            headers={"Authorization": f"Bearer {token}"},
            json={"enabled": False},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["enabled"] is False

        async with AsyncSessionLocal() as s:
            refreshed = await s.get(VisaDestination, dest.id)
            assert refreshed is not None
            assert refreshed.enabled is False

        pub = await client.get("/api/v2/destinations")
        assert pub.status_code == 200
        codes = {d["country_code"] for d in pub.json()["data"]}
        assert "US" not in codes

        # Re-enable
        r2 = await client.post(
            f"/api/v2/admin/config/countries/{country.id}/toggle",
            headers={"Authorization": f"Bearer {token}"},
            json={"enabled": True},
        )
        assert r2.status_code == 200
        pub2 = await client.get("/api/v2/destinations")
        codes2 = {d["country_code"] for d in pub2.json()["data"]}
        assert "US" in codes2
