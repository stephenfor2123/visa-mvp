# ADR-0003: Payment integration — `MockPayment` for V2, Stripe for V2.1

- **Status**: Accepted
- **Date**: 2026-06-15
- **Scope**: Backend `app/services/payment/` and `app/api/v2/payment.py`

## Context

The MVP needs to demonstrate a working payment flow end-to-end (create → user pays → notify → order transitions to `paid`) **before** any real PSP credentials are provisioned. Constraints:

- The first release (V2) targets demo, internal QA, and signed-off sandbox testing — **no real money must move**.
- Order state machine, signature verification, idempotency, and `BizException` error paths (see ADR-0005) must be exercised against a real-ish provider so the wiring is honest.
- Real PSP onboarding takes 4–6 weeks (KYC, webhook domain allow-list, settlement account) and is on the V2.1 critical path.

### Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Hard-code "paid" in `payment.py` for V2 | Smallest surface. | Defeats the purpose: webhook, signature, and idempotency stay untested; V2.1 will ship with no regression net. |
| Full Stripe sandbox now | Real Stripe SDK + webhook signing. | Requires real Stripe test account; webhook tunneling (`stripe-cli listen`) fragile on CI runners; introduces non-determinism too early. |
| **`MockPaymentProvider` implementing the same `PaymentAdapter` interface as Stripe** | Lets the rest of the system stay provider-agnostic; webhook + signature + idempotency are still exercised; switch to Stripe is a one-line `factory` change. | Must be kept honest (no `if provider == "mock": skip_signature_check` short-circuits). |

## Decision

We adopt **`MockPaymentProvider` for V2** behind the `PaymentAdapter` interface, with **Stripe (`StripePaymentProvider`) targeted for V2.1** as a drop-in replacement.

Concretely:

- `app/services/payment/adapter.py` defines the abstract `PaymentAdapter` with `create`, `confirm`, `query`, `close`, plus `verify_webhook_signature`.
- `app/services/payment/mock.py` implements `MockPaymentAdapter` that:
  - Generates deterministic mock transaction IDs (`mock_txn_{order_id}_{ts}`).
  - Self-calls `POST /api/v2/payment/notify` after a configurable delay (default 1 s) so the full create→notify→order-state-transition path runs in tests.
  - Signs its own webhook bodies with HMAC-SHA256 so the real signature-verification code is exercised.
- `app/services/payment/factory.py` returns `MockPaymentAdapter()` for V2; V2.1 will return `StripePaymentProvider()` based on env config (`PAYMENT_PROVIDER=stripe`).
- `app/services/payment_provider.py` keeps the legacy V1 `PaymentProvider` shim for backwards compatibility but V2 routes only use the new `payment/*` adapter.
- **The V2 release ships with `MockPayment` and a banner in the admin dashboard warning that test payments are in use.** Stripe is the only production target and the contract for V2.1 is documented (see `docs/stripe-credentials-setup.md`).

## Consequences

### Positive

- V2 demos, QA, and the e2e test suite exercise **the same code path** that production will use in V2.1 — no re-plumbing required on switch.
- Webhook signature verification, idempotency keys, and `BizException`-based error envelopes are tested against real-shaped payloads.
- Stripe upgrade is a configuration change (`PAYMENT_PROVIDER=stripe`) plus providing credentials — no service-layer refactor expected.
- Demo environments are deterministic: test IDs are reproducible from `order_id` + timestamp, screenshots / recordings are stable.

### Negative / Trade-offs

- The `MockPaymentAdapter` itself must be maintained. Risk: developers may forget to keep it 1:1 with the real Stripe interface. **Mitigation**: a contract test (`tests/payment/test_adapter_contract.py`) runs against both `MockPaymentAdapter` and a recorded Stripe replay fixture.
- Demo environments must clearly mark themselves as non-production; an admin-banner and a per-environment theme color are used.
- A small subset of Stripe-specific behaviours (3DS challenge UI, dispute webhooks, refund-as-negative-charge) is out of scope for V2; deferred to V2.1.

### Reversibility

Low. Swapping the provider is a `factory` change, but V2.1 also implies the `PaymentAdapter` surface is the contract. Changing the contract later would require re-implementing both adapters.

## References

- `backend/app/services/payment/adapter.py` — Abstract `PaymentAdapter`.
- `backend/app/services/payment/mock.py` — `MockPaymentAdapter` (V2).
- `backend/app/services/payment_provider.py` — Legacy V1 shim + V2.1 `StripePaymentProvider` placeholder.
- `backend/app/api/v2/payment.py` — Routes that exercise the adapter.
- `docs/stripe-credentials-setup.md` — V2.1 onboarding runbook.