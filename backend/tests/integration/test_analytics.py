"""Integration tests for /api/v2/analytics/track + pay-first funnel keys."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_track_anonymous_page_view(client):
    r = await client.post(
        "/api/v2/analytics/track",
        json={
            "event": "page_view",
            "session_id": "test-session-1",
            "path": "/home",
            "props": {"name": "Home"},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == "1000"
    assert body["data"]["event"] == "page_view"
    assert body["data"]["event_id"] > 0


@pytest.mark.asyncio
async def test_track_unknown_event_rejected(client):
    r = await client.post(
        "/api/v2/analytics/track",
        json={"event": "not_a_real_event", "session_id": "x"},
    )
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["code"] == "1001"


@pytest.mark.asyncio
async def test_track_country_selected(client):
    r = await client.post(
        "/api/v2/analytics/track",
        json={
            "event": "country_selected",
            "session_id": "test-session-2",
            "country_code": "US",
            "props": {"entry_source": "home"},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["code"] == "1000"
