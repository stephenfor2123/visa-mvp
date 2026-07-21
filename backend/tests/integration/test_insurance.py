"""Integration tests for /api/v2/insurance/* — B-W8-3 拒签险 service.

Covers (3 cases per W8-3 spec, 5 here for better signal):
  - test_insurance_factory: get_insurance_provider() returns the same
    MockInsuranceProvider singleton (and a fresh one after reset).
  - test_insurance_quote_bind: full quote → bind flow returns a
    consistent policy_no and `status="bound"`.
  - test_insurance_claim_approved: quote → bind → claim all return 200
    and the claim always comes back with `status="approved"` +
    `payout_cents == coverage_cents`.

Locked behavior:
  - POST /api/v2/insurance/quote → {quote_id, policy_no, premium_cents,
    coverage_cents, currency, created_at}
  - POST /api/v2/insurance/bind  → {policy_id, policy_no, status=bound,
    bound_at, premium_cents, coverage_cents, currency}
  - POST /api/v2/insurance/claim  → {claim_id, policy_id, status=approved,
    payout_cents == coverage_cents, approved_at}
  - GET  /api/v2/insurance/{policy_id} returns the same shape as bind
    for the bound state, and adds claim_id / claim_status after claim.

Zero credentials: no PA_INSURE_* / ZHONGAN_* env vars; the mock provider
computes premium purely from `(applicant_age, destination_country)`.
"""
from __future__ import annotations

import pytest

from app.services.insurance_provider import (
    InsuranceProvider,
    MockInsuranceProvider,
    get_insurance_provider,
    reset_insurance_provider_for_tests,
)


# ----------------------------------------------------------------- #
# Fixtures                                                            #
# ----------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolate_provider():
    """Each test gets a fresh in-memory policy store."""
    reset_insurance_provider_for_tests()
    yield
    reset_insurance_provider_for_tests()


async def _bearer_token(client, phone: str) -> str:
    """Register or reuse account keyed by phone → returns access token."""
    uname = f"u{phone}"
    email = f"{phone}@test.local"
    pwd = "Test1234"
    await client.post(
        "/api/v2/auth/register",
        json={"username": uname, "email": email, "password": pwd, "email_code": "123456", "age_confirmed_16": True},
    )
    r = await client.post(
        "/api/v2/auth/login",
        json={"account": email, "password": pwd},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ----------------------------------------------------------------- #
# 1. test_insurance_factory                                           #
# ----------------------------------------------------------------- #
class TestInsuranceFactory:
    def test_factory_returns_mock_singleton(self):
        p1 = get_insurance_provider()
        p2 = get_insurance_provider()
        assert isinstance(p1, MockInsuranceProvider)
        assert isinstance(p2, MockInsuranceProvider)
        assert p1 is p2, "factory must return the same singleton across calls"

    def test_factory_returns_fresh_after_reset(self):
        p1 = get_insurance_provider()
        reset_insurance_provider_for_tests()
        p2 = get_insurance_provider()
        assert p1 is not p2, "reset_insurance_provider_for_tests must drop the singleton"

    def test_factory_returns_abc_compatible_instance(self):
        # ABC contract — the singleton must satisfy the abstract type so a
        # V2.1 swap (PacificInsuranceProvider) is a drop-in.
        p = get_insurance_provider()
        assert isinstance(p, InsuranceProvider)


# ----------------------------------------------------------------- #
# 2. test_insurance_quote_bind                                        #
# ----------------------------------------------------------------- #
class TestInsuranceQuoteBind:
    async def test_quote_then_bind_full_flow(self, client):
        token = await _bearer_token(client, "13900139001")
        order_id = "V2-20260612-00001"
        # 1) Quote
        rq = await client.post(
            "/api/v2/insurance/quote",
            json={"order_id": order_id, "applicant_age": 28, "destination_country": "US"},
            headers=_auth(token),
        )
        assert rq.status_code == 200, rq.text
        qbody = rq.json()
        assert qbody["code"] == "1000"
        qdata = qbody["data"]
        assert qdata["quote_id"].startswith("MOCK-INS-")
        assert qdata["policy_no"] == qdata["quote_id"], "mock uses policy_no as quote_id"
        assert qdata["premium_cents"] == 9900, "base premium (age 28, US low-risk) = ¥99"
        assert qdata["coverage_cents"] == 99_000, "coverage = 10x premium"
        assert qdata["currency"] == "CNY"

        # 2) Bind
        rb = await client.post(
            "/api/v2/insurance/bind",
            json={"order_id": order_id, "quote_id": qdata["quote_id"]},
            headers=_auth(token),
        )
        assert rb.status_code == 200, rb.text
        bdata = rb.json()["data"]
        assert bdata["status"] == "bound"
        assert bdata["policy_no"] == qdata["policy_no"]
        assert bdata["policy_id"] == qdata["quote_id"]
        assert bdata["premium_cents"] == qdata["premium_cents"]
        assert bdata["coverage_cents"] == qdata["coverage_cents"]
        assert bdata["bound_at"], "bound_at must be set"

    async def test_bind_is_idempotent(self, client):
        token = await _bearer_token(client, "13900139002")
        order_id = "V2-20260612-00002"
        rq = await client.post(
            "/api/v2/insurance/quote",
            json={"order_id": order_id, "applicant_age": 35, "destination_country": "US"},
            headers=_auth(token),
        )
        quote_id = rq.json()["data"]["quote_id"]
        # First bind
        rb1 = await client.post(
            "/api/v2/insurance/bind",
            json={"order_id": order_id, "quote_id": quote_id},
            headers=_auth(token),
        )
        assert rb1.status_code == 200
        # Second bind — same call, must succeed (idempotent replay).
        rb2 = await client.post(
            "/api/v2/insurance/bind",
            json={"order_id": order_id, "quote_id": quote_id},
            headers=_auth(token),
        )
        assert rb2.status_code == 200
        b1 = rb1.json()["data"]
        b2 = rb2.json()["data"]
        assert b1["policy_id"] == b2["policy_id"]
        assert b1["bound_at"] == b2["bound_at"]

    async def test_quote_age_surcharge_for_older_applicant(self, client):
        token = await _bearer_token(client, "13900139003")
        rq = await client.post(
            "/api/v2/insurance/quote",
            json={"order_id": "V2-20260612-00003", "applicant_age": 50, "destination_country": "US"},
            headers=_auth(token),
        )
        assert rq.status_code == 200, rq.text
        premium = rq.json()["data"]["premium_cents"]
        # base 9900 + (50-30)*100 = 9900 + 2000 = 11900
        assert premium == 11900, f"age 50 surcharge should be 11900, got {premium}"

    async def test_quote_high_risk_country_multiplier(self, client):
        token = await _bearer_token(client, "13900139004")
        rq = await client.post(
            "/api/v2/insurance/quote",
            json={"order_id": "V2-20260612-00004", "applicant_age": 30, "destination_country": "BR"},
            headers=_auth(token),
        )
        assert rq.status_code == 200, rq.text
        premium = rq.json()["data"]["premium_cents"]
        # base 9900 * 1.2 = 11880 (no age surcharge at 30)
        assert premium == 11880, f"BR high-risk multiplier should give 11880, got {premium}"


# ----------------------------------------------------------------- #
# 3. test_insurance_claim_approved                                    #
# ----------------------------------------------------------------- #
class TestInsuranceClaimApproved:
    async def test_quote_bind_claim_full_lifecycle(self, client):
        token = await _bearer_token(client, "13900139010")
        order_id = "V2-20260612-00010"

        # 1) Quote
        rq = await client.post(
            "/api/v2/insurance/quote",
            json={"order_id": order_id, "applicant_age": 30, "destination_country": "GB"},
            headers=_auth(token),
        )
        assert rq.status_code == 200, rq.text
        quote = rq.json()["data"]

        # 2) Bind
        rb = await client.post(
            "/api/v2/insurance/bind",
            json={"order_id": order_id, "quote_id": quote["quote_id"]},
            headers=_auth(token),
        )
        assert rb.status_code == 200
        bound = rb.json()["data"]
        assert bound["status"] == "bound"

        # 3) Claim
        rc = await client.post(
            "/api/v2/insurance/claim",
            json={
                "order_id": order_id,
                "rejection_reason": "Section 4.2(a) insufficient financial ties",
            },
            headers=_auth(token),
        )
        assert rc.status_code == 200, rc.text
        claim = rc.json()["data"]
        assert claim["status"] == "approved", "mock must always approve"
        assert claim["payout_cents"] == bound["coverage_cents"]
        assert claim["payout_cents"] == quote["coverage_cents"]
        assert claim["policy_id"] == bound["policy_id"]
        assert claim["claim_id"].startswith("MOCK-CLM-")
        assert claim["rejection_reason"].startswith("Section 4.2")

        # 4) GET /{policy_id} now reflects the claimed state.
        rg = await client.get(
            f"/api/v2/insurance/{bound['policy_id']}",
            headers=_auth(token),
        )
        assert rg.status_code == 200, rg.text
        snap = rg.json()["data"]
        assert snap["status"] == "claimed"
        assert snap["claim_id"] == claim["claim_id"]
        assert snap["claim_status"] == "approved"
        assert snap["payout_cents"] == bound["coverage_cents"]

    async def test_claim_without_bind_returns_404(self, client):
        token = await _bearer_token(client, "13900139011")
        rc = await client.post(
            "/api/v2/insurance/claim",
            json={"order_id": "V2-20260612-NO-POLICY", "rejection_reason": "fake"},
            headers=_auth(token),
        )
        assert rc.status_code == 404
        assert rc.json()["code"] == "1004"

    async def test_quote_requires_jwt(self, client):
        r = await client.post(
            "/api/v2/insurance/quote",
            json={"order_id": "V2-X", "applicant_age": 30, "destination_country": "US"},
        )
        assert r.status_code in (401, 403), f"missing JWT should be 401/403, got {r.status_code}"

    async def test_get_policy_unknown_returns_404(self, client):
        token = await _bearer_token(client, "13900139012")
        rg = await client.get(
            "/api/v2/insurance/MOCK-INS-DOES-NOT-EXIST",
            headers=_auth(token),
        )
        assert rg.status_code == 404
        assert rg.json()["code"] == "1004"
