"""B-W8-3 — Standalone Insurance provider (V2 §4.6, Mock-only for V2).

Scope:
  - `InsuranceProvider` ABC (3 methods: quote / bind / claim)
  - `MockInsuranceProvider` — the only implementation in V2 (no 太平洋保险 /
    众安保险 / Ping An / ZhongAn SDK is wired in V2; that lands in V2.1).
  - In-memory dict keyed by `policy_id` storing the full policy lifecycle
    (quote → bound → claimed).
  - Zero credentials: no PA_INSURE_*, no ZHONGAN_*, no TAIPING_* env vars.
  - `claim` always returns `status="approved"` in mock mode — the Mavis
    13:13 拍板 "拒签险全 Mock, 后期 V2.1 阶段再接真保司 SDK" means we cannot
    let the demo hang on a real-world KYC + underwriting pipeline.

DoD-locked behaviors:
  - `quote(order_id, applicant_age, destination_country)` returns
    `{quote_id, premium_cents, currency, coverage_cents, policy_no,
      created_at}`. The `policy_no` is the lookup key for the bind step.
  - `bind(order_id, quote_id)` returns `{policy_id, policy_no, status=bound,
      bound_at, order_id, coverage_cents, premium_cents, currency}` and
    marks the policy active.
  - `claim(order_id, rejection_reason)` returns
    `{claim_id, policy_id, status="approved", payout_cents, approved_at,
      order_id, rejection_reason}`. Mock always approves; real channel will
    verify the rejection document (v2.1, 太平洋 OCR + claim ops).

Coexistence with future real-channel adapter (V2.1):
  - The ABC's return shapes are deliberately JSON-friendly (no dataclasses
    leaking out) so a future `PacificInsuranceProvider` can drop in by
    returning the same dict keys.
  - The factory `get_insurance_provider()` is a singleton seam — swap in
    a real provider by reading `settings.insurance_channel`.

Why we don't import `app.core.config` here: the mock is credential-free,
so the module must remain importable from tests without a Settings object.
The settings.insurance_channel swap is a V2.1 concern.
"""
import secrets
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Union

from loguru import logger


_log = logger.bind(component="insurance_provider")


# --------------------------------------------------------------------------- #
# Errors (module-local — provider-level, not Biz).                            #
# --------------------------------------------------------------------------- #
class InsuranceProviderError(Exception):
    """Base for provider-level errors."""


class PolicyNotFound(InsuranceProviderError):
    """The supplied policy_id / quote_id has no record."""


class PolicyAlreadyBound(InsuranceProviderError):
    """Tried to bind a quote that already has a bound policy."""


class PolicyNotBound(InsuranceProviderError):
    """Tried to claim a policy that was quoted but not yet bound."""


# --------------------------------------------------------------------------- #
# Internal data shape                                                         #
# --------------------------------------------------------------------------- #
@dataclass
class _StoredPolicy:
    policy_id: str          # unique policy key (e.g. "INS-...")
    policy_no: str          # human-facing number (e.g. "MOCK-INS-...")
    order_id: str
    user_id: str            # Owner user ID (for IDOR prevention)
    applicant_age: int
    destination_country: str
    premium_cents: int
    coverage_cents: int
    currency: str
    status: str             #Union[quoted, bound, claimed]
    created_at: datetime
    bound_at: Optional[datetime] = None
    claim_id: Optional[str] = None
    payout_cents: Optional[int] = None
    claim_status: Optional[str] = None
    rejection_reason: Optional[str] = None
    claimed_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# Abstract base                                                                #
# --------------------------------------------------------------------------- #
class InsuranceProvider(ABC):
    """V2 §4.6 拒签险 service — single ABC.

    Quote is free (no underwrite in mock); bind locks the policy to an
    order; claim pays out if the underlying visa application is rejected.
    """

    @abstractmethod
    async def quote(
        self,
        *,
        order_id: str,
        applicant_age: int,
        destination_country: str,
    ) -> dict:
        """Generate a non-binding price quote for the order.

        Returns a dict:
            {
              "ok": True,
              "quote_id": str,             # short-lived token, also stored on policy
              "policy_no": str,            # the lookup key passed to bind()
              "premium_cents": int,
              "coverage_cents": int,
              "currency": str,
              "created_at": str,           # ISO8601 UTC
            }
        Implementations should NOT raise on transient upstream failures —
        return `ok=False` with `error` instead. (Mock always succeeds.)
        """
        raise NotImplementedError

    @abstractmethod
    async def bind(
        self,
        *,
        order_id: str,
        quote_id: str,
    ) -> dict:
        """Bind a quote to a concrete policy on the order.

        Returns a dict:
            {
              "ok": True,
              "policy_id": str,
              "policy_no": str,
              "status": "bound",
              "bound_at": str,
              "order_id": str,
              "premium_cents": int,
              "coverage_cents": int,
              "currency": str,
            }
        Idempotency: a second bind for the same (order_id, quote_id) must
        return the existing policy (no second policy issued, no second
        premium charged).
        """
        raise NotImplementedError

    @abstractmethod
    async def claim(
        self,
        *,
        order_id: str,
        rejection_reason: str,
    ) -> dict:
        """File a claim against the bound policy. Mock always approves.

        Returns a dict:
            {
              "ok": True,
              "claim_id": str,
              "policy_id": str,
              "policy_no": str,
              "status": "approved",        # mock: always approved
              "payout_cents": int,         # == coverage_cents in mock
              "approved_at": str,
              "order_id": str,
              "rejection_reason": str,
            }
        """
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Mock implementation (V2 default)                                            #
# --------------------------------------------------------------------------- #
class MockInsuranceProvider(InsuranceProvider):
    """In-process mock. No external deps, no creds, no network.

    Premium model (deterministic, no surprise math in tests):
      base   = ¥99 = 9900 cents
      age surcharge = (applicant_age - 30) * 100 cents if age > 30 else 0
      country multiplier:
        Schengen/US/GB/JP/AU/SG/CA = 1.0
        high-risk (any other)       = 1.2
      premium = int(base * multiplier + age surcharge)

    Coverage = 10x premium, capped at 50 0000 cents (¥5000). This matches
    the V2 §4.6 spec: "赔付金额 = 签证服务费 + 机票改签费, 上限 ¥5000".
    """

    BASE_PREMIUM_CENTS = 9900
    MAX_COVERAGE_CENTS = 50_0000  # ¥5000.00
    # V2 §4.6 spec: 国家风险等级
    LOW_RISK_COUNTRIES = frozenset(
        ["US", "GB", "JP", "AU", "SG", "CA", "DE", "FR", "IT", "ES",
         "NL", "CH", "SE", "NO", "FI", "DK", "BE", "AT", "IE", "NZ",
         "KR", "MY", "TH", "VN", "ID", "PH"]
    )
    HIGH_RISK_MULTIPLIER = 1.2
    AGE_SURCHARGE_PER_YEAR = 100  # cents

    def __init__(self) -> None:
        self._policies: dict[str, _StoredPolicy] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # helpers                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _now_wall() -> datetime:
        return datetime.now(timezone.utc)

    def _gen_policy_no(self) -> str:
        # MOCK-INS-20260612-XXXXXXXX (8 hex chars); timezone is implicit UTC.
        return f"MOCK-INS-{int(time.time())}-{secrets.token_hex(4).upper()}"

    def _gen_claim_id(self) -> str:
        return f"MOCK-CLM-{int(time.time())}-{secrets.token_hex(4).upper()}"

    def _compute_premium(
        self, *, applicant_age: int, destination_country: str
    ) -> tuple[int, int]:
        """Return (premium_cents, coverage_cents). Pure function for testability."""
        if applicant_age < 0 or applicant_age > 120:
            raise ValueError(f"applicant_age out of range: {applicant_age}")

        mult = 1.0 if destination_country in self.LOW_RISK_COUNTRIES else self.HIGH_RISK_MULTIPLIER
        age_surcharge = max(0, applicant_age - 30) * self.AGE_SURCHARGE_PER_YEAR
        premium = int(self.BASE_PREMIUM_CENTS * mult) + age_surcharge
        # Coverage is 10x premium, capped at ¥5000 (per V2 §4.6).
        coverage = min(premium * 10, self.MAX_COVERAGE_CENTS)
        return premium, coverage

    # ------------------------------------------------------------------ #
    # InsuranceProvider ABC                                              #
    # ------------------------------------------------------------------ #
    async def quote(
        self,
        *,
        order_id: str,
        applicant_age: int,
        destination_country: str,
    ) -> dict:
        if not order_id or not isinstance(order_id, str):
            return {"ok": False, "error": "order_id is required"}
        if not destination_country or not isinstance(destination_country, str):
            return {"ok": False, "error": "destination_country is required"}

        try:
            premium, coverage = self._compute_premium(
                applicant_age=applicant_age, destination_country=destination_country
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        policy_no = self._gen_policy_no()
        # quote_id == policy_no (one-shot token; binding promotes it to policy_id)
        quote_id = policy_no
        now = self._now_wall()

        with self._lock:
            self._policies[policy_no] = _StoredPolicy(
                policy_id=policy_no,
                policy_no=policy_no,
                order_id=order_id,
                user_id="",  # Set during bind() once user_id is known
                applicant_age=applicant_age,
                destination_country=destination_country,
                premium_cents=premium,
                coverage_cents=coverage,
                currency="CNY",
                status="quoted",
                created_at=now,
            )

        _log.info(
            "insurance quote order_id={} country={} age={} premium_cents={} "
            "coverage_cents={} policy_no={}",
            order_id, destination_country, applicant_age, premium, coverage, policy_no,
        )
        return {
            "ok": True,
            "quote_id": quote_id,
            "policy_no": policy_no,
            "premium_cents": premium,
            "coverage_cents": coverage,
            "currency": "CNY",
            "created_at": now.isoformat(timespec="seconds"),
        }

    async def bind(
        self,
        *,
        order_id: str,
        quote_id: str,
        user_id: Optional[str] = None,
    ) -> dict:
        if not quote_id or not isinstance(quote_id, str):
            return {"ok": False, "error": "quote_id is required"}

        with self._lock:
            policy = self._policies.get(quote_id)
            if policy is None:
                return {"ok": False, "error": f"quote_id={quote_id} not found"}
            if policy.order_id != order_id:
                return {
                    "ok": False,
                    "error": (
                        f"order_id mismatch: policy belongs to {policy.order_id}, "
                        f"caller passed {order_id}"
                    ),
                }
            if policy.status == "claimed":
                return {
                    "ok": False,
                    "error": "policy already claimed; cannot rebind",
                }
            if policy.status == "bound":
                # Idempotent: return the existing policy verbatim.
                _log.info(
                    "insurance bind idempotent replay order_id={} policy_no={}",
                    order_id, policy.policy_no,
                )
                return {
                    "ok": True,
                    "policy_id": policy.policy_id,
                    "policy_no": policy.policy_no,
                    "status": "bound",
                    "bound_at": policy.bound_at.isoformat(timespec="seconds") if policy.bound_at else None,
                    "order_id": policy.order_id,
                    "premium_cents": policy.premium_cents,
                    "coverage_cents": policy.coverage_cents,
                    "currency": policy.currency,
                }
            # quoted → bound — record owner user_id for IDOR prevention
            policy.status = "bound"
            policy.bound_at = self._now_wall()
            policy.user_id = user_id or ""
            snapshot = policy

        _log.info(
            "insurance bound order_id={} policy_no={} premium_cents={}",
            order_id, snapshot.policy_no, snapshot.premium_cents,
        )
        return {
            "ok": True,
            "policy_id": snapshot.policy_id,
            "policy_no": snapshot.policy_no,
            "status": "bound",
            "bound_at": snapshot.bound_at.isoformat(timespec="seconds"),
            "order_id": snapshot.order_id,
            "premium_cents": snapshot.premium_cents,
            "coverage_cents": snapshot.coverage_cents,
            "currency": snapshot.currency,
        }

    async def claim(
        self,
        *,
        order_id: str,
        rejection_reason: str,
    ) -> dict:
        if not order_id or not isinstance(order_id, str):
            return {"ok": False, "error": "order_id is required"}
        rejection_reason = (rejection_reason or "").strip()
        if not rejection_reason:
            return {"ok": False, "error": "rejection_reason is required"}

        with self._lock:
            # Find the bound policy for this order. Latest one wins.
            candidates = [
                p for p in self._policies.values()
                if p.order_id == order_id and p.status in ("bound", "claimed")
            ]
            if not candidates:
                return {
                    "ok": False,
                    "error": f"no bound policy found for order_id={order_id}",
                }
            policy = max(candidates, key=lambda p: p.bound_at or p.created_at)
            if policy.status == "claimed":
                # Idempotent claim — return the existing claim.
                _log.info(
                    "insurance claim idempotent replay order_id={} claim_id={}",
                    order_id, policy.claim_id,
                )
                return {
                    "ok": True,
                    "claim_id": policy.claim_id,
                    "policy_id": policy.policy_id,
                    "policy_no": policy.policy_no,
                    "status": policy.claim_status or "approved",
                    "payout_cents": policy.payout_cents or 0,
                    "approved_at": policy.claimed_at.isoformat(timespec="seconds") if policy.claimed_at else None,
                    "order_id": policy.order_id,
                    "rejection_reason": policy.rejection_reason or "",
                }
            # bound → claimed (mock: always approve)
            now = self._now_wall()
            claim_id = self._gen_claim_id()
            policy.status = "claimed"
            policy.claim_id = claim_id
            policy.payout_cents = policy.coverage_cents
            policy.claim_status = "approved"
            policy.rejection_reason = rejection_reason
            policy.claimed_at = now

        _log.info(
            "insurance claim approved order_id={} policy_no={} claim_id={} "
            "payout_cents={}",
            order_id, policy.policy_no, claim_id, policy.payout_cents,
        )
        return {
            "ok": True,
            "claim_id": claim_id,
            "policy_id": policy.policy_id,
            "policy_no": policy.policy_no,
            "status": "approved",
            "payout_cents": policy.payout_cents,
            "approved_at": now.isoformat(timespec="seconds"),
            "order_id": policy.order_id,
            "rejection_reason": rejection_reason,
        }

    # ------------------------------------------------------------------ #
    # Read helpers (used by GET /api/v2/insurance/{policy_id})            #
    # ------------------------------------------------------------------ #
    def get_policy(
        self, policy_id: str, owner_user_id: Optional[str] = None
    ) -> Optional[dict]:
        """Return a flat dict snapshot of a policy, or None if not found.

        Parameters
        ----------
        policy_id : str
            The policy ID to look up.
        owner_user_id : Optional[str]
            If provided, verifies the policy belongs to this user. Returns None
            (not an error) if the policy exists but belongs to another user,
            preventing IDOR. Prevents callers from probing arbitrary policy IDs.
        """
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                return None

            # IDOR check: if caller provides owner_user_id, verify ownership
            if owner_user_id is not None and p.user_id and p.user_id != owner_user_id:
                return None

            return {
                "policy_id": p.policy_id,
                "policy_no": p.policy_no,
                "order_id": p.order_id,
                "status": p.status,
                "applicant_age": p.applicant_age,
                "destination_country": p.destination_country,
                "premium_cents": p.premium_cents,
                "coverage_cents": p.coverage_cents,
                "currency": p.currency,
                "created_at": p.created_at.isoformat(timespec="seconds"),
                "bound_at": p.bound_at.isoformat(timespec="seconds") if p.bound_at else None,
                "claim_id": p.claim_id,
                "claim_status": p.claim_status,
                "payout_cents": p.payout_cents,
                "claimed_at": p.claimed_at.isoformat(timespec="seconds") if p.claimed_at else None,
                "rejection_reason": p.rejection_reason,
            }


# --------------------------------------------------------------------------- #
# Factory — single source of truth                                            #
# --------------------------------------------------------------------------- #
_provider_singleton: Optional[InsuranceProvider] = None
_provider_lock = threading.Lock()


def get_insurance_provider() -> InsuranceProvider:
    """Return the process-wide MockInsuranceProvider (V2 default).

    V2.1 swap: read `settings.insurance_channel`, return
    `PacificInsuranceProvider` if "pacific" is set. For V2 we hard-code
    mock to satisfy the "零凭据 / 1-2d 可跑" rule.
    """
    global _provider_singleton
    with _provider_lock:
        if _provider_singleton is None:
            _provider_singleton = MockInsuranceProvider()
        return _provider_singleton


def reset_insurance_provider_for_tests() -> None:
    """Drop the singleton — used by pytest to start each test with a clean store."""
    global _provider_singleton
    with _provider_lock:
        _provider_singleton = None


__all__ = [
    "InsuranceProvider",
    "MockInsuranceProvider",
    "InsuranceProviderError",
    "PolicyNotFound",
    "PolicyAlreadyBound",
    "PolicyNotBound",
    "get_insurance_provider",
    "reset_insurance_provider_for_tests",
]


# --------------------------------------------------------------------------- #
# V2.1 TODO — replace Mock with real insurance channel                          #
# --------------------------------------------------------------------------- #
# When product signs off (Mavis 13:13: "拒签险全 Mock, 后期 V2.1 阶段再接真保司
# SDK → 太平洋保险 / 众安保险 任选"), the swap is:
#
#   1. Add `PacificInsuranceProvider` (or `ZhongAnInsuranceProvider`) under
#      `app/services/insurance/adapter.py` implementing the same ABC
#      (quote / bind / claim).
#   2. Channel-select via `Settings.insurance_channel:
#      Literal["mock", "pacific", "zhongan"]` (zero credentials in `dev`).
#   3. The facade in this file stays unchanged: it already speaks in
#      (order_id, applicant_age, destination_country) / (premium_cents,
#      coverage_cents, payout_cents), which is exactly what the API +
#      audit + E2E tests need. Only `_gen_*_no()` and the auto-quote
#      hooks in `/api/v2/insurance/quote` swap over to the real signed
#      underwriting flow.
#
# Until then, no PA_INSURE_* / ZHONGAN_* / TAIPING_* env vars exist, and
# this provider can be exercised end-to-end with `pytest` alone.
