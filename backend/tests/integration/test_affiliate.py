"""Integration tests for /api/v2/affiliate/* — B-W8-4 standalone Affiliate service.

Covers (4 cases, 13 sub-cases):
  - test_affiliate_factory: MockAffiliateProvider factory + singleton + reset
  - test_affiliate_track_attribute: track → attribute end-to-end + idempotency
  - test_affiliate_commission_calc: commission computed from order_total × 5%
  - test_affiliate_payout: payout 100% paid + partner stats rollup

Locked behavior:
  - POST /api/v2/affiliate/track      → 1000 with {click_id, aff_code, partner_id}
  - POST /api/v2/affiliate/attribute  → 1000 with {attributed: True}
  - GET  /api/v2/affiliate/commission/{order_id}?order_total_cents=N → 5% rule
  - POST /api/v2/affiliate/payout     → 1000 with {status: "paid", payout_id}
  - GET  /api/v2/affiliate/{partner_id}/stats (X-Partner-Key) → rollup
  - 4xx surfaces the V2 envelope: {code, message, data}
"""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.affiliate_provider import (
    AffiliateProvider,
    InvalidPayoutPeriod,
    MockAffiliateProvider,
    PayoutBelowFloor,
    UnknownClick,
    UnknownOrder,
    get_affiliate_provider,
    reset_affiliate_provider_for_tests,
)


# ----------------------------------------------------------------- #
# Helpers                                                            #
# ----------------------------------------------------------------- #
def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, phone: str) -> str:
    """SMS-login -> access token. Auto-registers on first use (mock mode)."""
    r = await client.post(
        "/api/v2/auth/sms-login",
        json={"phone": phone, "phone_country": "+86", "sms_code": "123456"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


# ----------------------------------------------------------------- #
# Per-test isolation: fresh in-memory store + fresh app             #
# ----------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolate_provider():
    """Each test gets a fresh in-memory store (clicks / attribs / payouts all empty)."""
    reset_affiliate_provider_for_tests()
    yield
    reset_affiliate_provider_for_tests()


# ----------------------------------------------------------------- #
# 1. test_affiliate_factory                                          #
# ----------------------------------------------------------------- #
class TestAffiliateFactory:
    def test_factory_returns_mock_singleton(self):
        p1 = get_affiliate_provider()
        p2 = get_affiliate_provider()
        assert isinstance(p1, MockAffiliateProvider)
        assert isinstance(p2, MockAffiliateProvider)
        assert p1 is p2, "factory must return the same singleton across calls"

    def test_factory_returns_abc(self):
        """ABC and singleton contract — get_affiliate_provider must
        return *something* that satisfies the ABC interface."""
        p = get_affiliate_provider()
        assert isinstance(p, AffiliateProvider)
        for method in ("track", "attribute", "commission", "payout"):
            assert hasattr(p, method), f"MockAffiliateProvider missing {method}"

    def test_factory_returns_fresh_after_reset(self):
        p1 = get_affiliate_provider()
        reset_affiliate_provider_for_tests()
        p2 = get_affiliate_provider()
        assert p1 is not p2, "reset_affiliate_provider_for_tests must drop the singleton"

    def test_mock_provider_rejects_bad_rate(self):
        from decimal import Decimal
        with pytest.raises(ValueError):
            MockAffiliateProvider(commission_rate=Decimal("0"))
        with pytest.raises(ValueError):
            MockAffiliateProvider(commission_rate=Decimal("1.5"))


# ----------------------------------------------------------------- #
# 2. test_affiliate_track_attribute                                  #
# ----------------------------------------------------------------- #
class TestTrackAttribute:
    async def test_track_returns_click_and_partner(self, client):
        token = await _register(client, "13855551001")
        r = await client.post(
            "/api/v2/affiliate/track",
            json={"aff_code": "AFF123", "click_id": "click_abc", "landing_path": "/visa/india"},
            headers=_bearer(token),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "1000"
        data = body["data"]
        assert data["click_id"] == "click_abc"
        assert data["aff_code"] == "AFF123"
        assert data["partner_id"] == "PARTNER_AFF123"
        assert data["tracked_at"]

    async def test_track_idempotent_on_same_click_id(self, client):
        """Re-tracking the same click_id is a no-op (returns the same record)."""
        token = await _register(client, "13855551002")
        h = _bearer(token)
        r1 = await client.post(
            "/api/v2/affiliate/track",
            json={"aff_code": "AFF999", "click_id": "click_dedup"},
            headers=h,
        )
        r2 = await client.post(
            "/api/v2/affiliate/track",
            json={"aff_code": "AFF999", "click_id": "click_dedup"},
            headers=h,
        )
        assert r1.status_code == r2.status_code == 200
        assert r1.json()["data"]["click_id"] == r2.json()["data"]["click_id"]
        assert r1.json()["data"]["tracked_at"] == r2.json()["data"]["tracked_at"]

    async def test_attribute_after_track_binds_order(self, client):
        token = await _register(client, "13855551003")
        h = _bearer(token)
        # 1) track
        track_r = await client.post(
            "/api/v2/affiliate/track",
            json={"aff_code": "AFF123", "click_id": "click_xyz"},
            headers=h,
        )
        assert track_r.status_code == 200
        # 2) attribute
        attr_r = await client.post(
            "/api/v2/affiliate/attribute",
            json={"order_id": "ORD-001", "click_id": "click_xyz"},
            headers=h,
        )
        assert attr_r.status_code == 200, attr_r.text
        data = attr_r.json()["data"]
        assert data["order_id"] == "ORD-001"
        assert data["click_id"] == "click_xyz"
        assert data["aff_code"] == "AFF123"
        assert data["partner_id"] == "PARTNER_AFF123"
        assert data["attributed"] is True
        assert data["attributed_at"]

    async def test_attribute_unknown_click_returns_404(self, client):
        token = await _register(client, "13855551004")
        r = await client.post(
            "/api/v2/affiliate/attribute",
            json={"order_id": "ORD-002", "click_id": "click_never_tracked"},
            headers=_bearer(token),
        )
        assert r.status_code == 404
        assert r.json()["code"] == "1004"  # NOT_FOUND

    async def test_attribute_idempotent_on_same_order(self, client):
        """Re-attributing the same order is a no-op (returns the same record)."""
        token = await _register(client, "13855551005")
        h = _bearer(token)
        await client.post(
            "/api/v2/affiliate/track",
            json={"aff_code": "AFF123", "click_id": "click_q"},
            headers=h,
        )
        r1 = await client.post(
            "/api/v2/affiliate/attribute",
            json={"order_id": "ORD-003", "click_id": "click_q"},
            headers=h,
        )
        r2 = await client.post(
            "/api/v2/affiliate/attribute",
            json={"order_id": "ORD-003", "click_id": "click_q"},
            headers=h,
        )
        assert r1.status_code == r2.status_code == 200
        assert r1.json()["data"]["attributed_at"] == r2.json()["data"]["attributed_at"]

    async def test_track_requires_auth(self, client):
        r = await client.post(
            "/api/v2/affiliate/track",
            json={"aff_code": "AFF123", "click_id": "click_xyz"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "1005"  # UNAUTHORIZED


# ----------------------------------------------------------------- #
# 3. test_affiliate_commission_calc                                  #
# ----------------------------------------------------------------- #
class TestCommissionCalc:
    async def test_commission_is_5_percent_of_order_total(self, client):
        """$200 order (20000 cents) × 5% = $10 (1000 cents)."""
        token = await _register(client, "13855551010")
        h = _bearer(token)
        # setup
        await client.post(
            "/api/v2/affiliate/track",
            json={"aff_code": "AFF100", "click_id": "click_c1"},
            headers=h,
        )
        await client.post(
            "/api/v2/affiliate/attribute",
            json={"order_id": "ORD-C100", "click_id": "click_c1"},
            headers=h,
        )
        # query commission with explicit order total
        r = await client.get(
            "/api/v2/affiliate/commission/ORD-C100",
            params={"order_total_cents": 20000},
            headers=h,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["order_id"] == "ORD-C100"
        assert data["commission_amount_cents"] == 1000, "5% of 20000 = 1000"
        assert data["commission_rate"] == "0.05"
        assert data["currency"] == "USD"
        assert data["partner_id"] == "PARTNER_AFF100"
        assert data["commission_id"].startswith("mock_comm_")

    async def test_commission_rounds_half_up(self, client):
        """$13.37 (1337 cents) × 5% = 66.85 cents → 67 cents (HALF_UP)."""
        token = await _register(client, "13855551011")
        h = _bearer(token)
        await client.post(
            "/api/v2/affiliate/track",
            json={"aff_code": "AFF100", "click_id": "click_c2"},
            headers=h,
        )
        await client.post(
            "/api/v2/affiliate/attribute",
            json={"order_id": "ORD-C200", "click_id": "click_c2"},
            headers=h,
        )
        r = await client.get(
            "/api/v2/affiliate/commission/ORD-C200",
            params={"order_total_cents": 1337},
            headers=h,
        )
        assert r.status_code == 200
        # 1337 * 0.05 = 66.85 → HALF_UP to 67
        assert r.json()["data"]["commission_amount_cents"] == 67

    async def test_commission_unknown_order_returns_404(self, client):
        token = await _register(client, "13855551012")
        r = await client.get(
            "/api/v2/affiliate/commission/ORD-NEVER",
            headers=_bearer(token),
        )
        assert r.status_code == 404
        assert r.json()["code"] == "1004"


# ----------------------------------------------------------------- #
# 4. test_affiliate_payout                                           #
# ----------------------------------------------------------------- #
class TestPayout:
    async def test_payout_settles_all_attributed_orders(self, client):
        token = await _register(client, "13855551020")
        h = _bearer(token)
        # 2 clicks → 2 attributed orders
        for i in range(2):
            await client.post(
                "/api/v2/affiliate/track",
                json={"aff_code": "AFF200", "click_id": f"click_p{i}"},
                headers=h,
            )
            await client.post(
                "/api/v2/affiliate/attribute",
                json={"order_id": f"ORD-P{i}", "click_id": f"click_p{i}"},
                headers=h,
            )
            # record commission for each
            await client.get(
                f"/api/v2/affiliate/commission/ORD-P{i}",
                params={"order_total_cents": 10000},  # $100 → $5 = 500 cents
                headers=h,
            )
        # settle monthly
        r = await client.post(
            "/api/v2/affiliate/payout",
            json={"partner_id": "PARTNER_AFF200", "period": "monthly"},
            headers=h,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["status"] == "paid"
        assert data["partner_id"] == "PARTNER_AFF200"
        assert data["period"] == "monthly"
        assert sorted(data["order_ids"]) == ["ORD-P0", "ORD-P1"]
        # 500 + 500 = 1000 cents
        assert data["total_amount_cents"] == 1000
        assert data["currency"] == "USD"
        assert data["payout_id"].startswith("mock_payout_")

    async def test_payout_idempotent_does_not_double_pay(self, client):
        """Second payout for the same partner with no new orders must 404
        (nothing to pay)."""
        token = await _register(client, "13855551021")
        h = _bearer(token)
        await client.post(
            "/api/v2/affiliate/track",
            json={"aff_code": "AFF200", "click_id": "click_p3"},
            headers=h,
        )
        await client.post(
            "/api/v2/affiliate/attribute",
            json={"order_id": "ORD-P3", "click_id": "click_p3"},
            headers=h,
        )
        await client.get(
            "/api/v2/affiliate/commission/ORD-P3",
            params={"order_total_cents": 10000},
            headers=h,
        )
        # first payout
        r1 = await client.post(
            "/api/v2/affiliate/payout",
            json={"partner_id": "PARTNER_AFF200", "period": "weekly"},
            headers=h,
        )
        assert r1.status_code == 200
        # second payout — nothing left to pay
        r2 = await client.post(
            "/api/v2/affiliate/payout",
            json={"partner_id": "PARTNER_AFF200", "period": "weekly"},
            headers=h,
        )
        assert r2.status_code == 404
        assert r2.json()["code"] == "1004"

    async def test_payout_invalid_period_returns_400(self, client):
        token = await _register(client, "13855551022")
        r = await client.post(
            "/api/v2/affiliate/payout",
            json={"partner_id": "PARTNER_AFF200", "period": "yearly"},
            headers=_bearer(token),
        )
        assert r.status_code == 400
        assert r.json()["code"] == "1001"  # INVALID_PARAMS

    async def test_partner_stats_rollup(self, client):
        token = await _register(client, "13855551030")
        h = _bearer(token)
        # Track 3 clicks, attribute 2, record commission, then payout
        for i in range(3):
            await client.post(
                "/api/v2/affiliate/track",
                json={"aff_code": "AFF300", "click_id": f"click_s{i}"},
                headers=h,
            )
        for i in range(2):
            await client.post(
                "/api/v2/affiliate/attribute",
                json={"order_id": f"ORD-S{i}", "click_id": f"click_s{i}"},
                headers=h,
            )
            await client.get(
                f"/api/v2/affiliate/commission/ORD-S{i}",
                params={"order_total_cents": 10000},
                headers=h,
            )
        # stats BEFORE payout
        settings = get_settings()
        r1 = await client.get(
            "/api/v2/affiliate/PARTNER_AFF300/stats",
            headers={"X-Partner-Key": settings.system_api_key},
        )
        assert r1.status_code == 200, r1.text
        d = r1.json()["data"]
        assert d["partner_id"] == "PARTNER_AFF300"
        assert d["click_count"] == 3
        assert d["attributed_count"] == 2
        assert d["commission_cents"] == 1000
        assert d["paid_cents"] == 0
        assert d["pending_cents"] == 1000
        assert sorted(d["orders"]) == ["ORD-S0", "ORD-S1"]
        # payout
        await client.post(
            "/api/v2/affiliate/payout",
            json={"partner_id": "PARTNER_AFF300", "period": "monthly"},
            headers=h,
        )
        # stats AFTER payout
        r2 = await client.get(
            "/api/v2/affiliate/PARTNER_AFF300/stats",
            headers={"X-Partner-Key": settings.system_api_key},
        )
        d2 = r2.json()["data"]
        assert d2["paid_cents"] == 1000
        assert d2["pending_cents"] == 0
        assert len(d2["payouts"]) == 1

    async def test_partner_stats_missing_key_returns_401(self, client):
        r = await client.get("/api/v2/affiliate/PARTNER_AFF300/stats")
        assert r.status_code == 401
        assert r.json()["code"] == "1005"

    async def test_partner_stats_wrong_key_returns_401(self, client):
        r = await client.get(
            "/api/v2/affiliate/PARTNER_AFF300/stats",
            headers={"X-Partner-Key": "wrong-key"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "1005"


# ----------------------------------------------------------------- #
# Direct provider-layer tests (no HTTP)                              #
# ----------------------------------------------------------------- #
class TestProviderDirect:
    async def test_provider_raises_specific_errors(self):
        provider = MockAffiliateProvider()
        # Unknown click → UnknownClick
        with pytest.raises(UnknownClick):
            await provider.attribute("ORD-1", "never-tracked")
        # Unknown order (no total) → UnknownOrder
        with pytest.raises(UnknownOrder):
            await provider.commission("ORD-never")
        # Invalid period → InvalidPayoutPeriod
        with pytest.raises(InvalidPayoutPeriod):
            await provider.payout("PARTNER_X", "yearly")
        # Nothing to pay → UnknownOrder
        with pytest.raises(UnknownOrder):
            await provider.payout("PARTNER_X", "monthly")

    async def test_payout_below_floor_rejected(self):
        """A commission of 50 cents (below the $1 floor) must refuse to pay."""
        from decimal import Decimal
        provider = MockAffiliateProvider(
            commission_rate=Decimal("0.005"),  # 0.5%
            min_payout_cents=100,              # $1 floor
        )
        await provider.track("AFF_X", click_id="c1")
        await provider.attribute("ORD-X1", "c1")
        # 10000 * 0.005 = 50 cents, below the floor
        await provider.commission("ORD-X1", order_total_cents=10000)
        with pytest.raises(PayoutBelowFloor):
            await provider.payout("PARTNER_AFF_X", "monthly")
