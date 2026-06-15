# ADR-0005: Error handling — `BizException` + `ErrorCode` enum as the unified contract

- **Status**: Accepted
- **Date**: 2026-06-15
- **Scope**: Backend (`backend/app/`)

## Context

The API is consumed by three clients (web, iOS, mini-program) and the admin dashboard. Every client needs a stable, machine-readable error contract so it can:

- Show a localized error message (driven by the i18n key in the response body).
- Decide whether to retry, prompt re-login, surface to the user, or escalate.
- Distinguish user-facing 4xx (validation, auth, business rules) from 5xx (infrastructure) for observability.

Without a single contract we end up with the classic mess — some endpoints raise `HTTPException(400, "User exists")`, some return `JSONResponse({"ok": false, "msg": "..."})`, some leak raw SQL errors, and clients end up with N independent parsing branches.

### Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Plain `HTTPException` everywhere | Built-in, zero abstraction. | String-only message, no code, no i18n key, inconsistent status mapping. |
| Custom `JSONResponse` returned directly per route | Trivially flexible. | Bypasses framework exception handlers; easy to forget status codes / headers; no DRY. |
| **`BizException` + `ErrorCode` enum + a single `exception_handler`** | One exception type, one structured payload, one global handler; enum prevents typos; status code + business code are co-located; easy to extend. | One layer of indirection for new contributors to learn. |

## Decision

We adopt a single error model:

- **`ErrorCode`** — a `str, Enum` declared in `backend/app/core/errors.py`, organised by domain:
  - `1xxx` — generic (validation, auth, rate-limit, server).
  - `2xxx` — auth (login, SMS, MFA, refresh tokens).
  - `3xxx` — user profile.
  - `4xxx` — order / payment (V2 §4.2).
  - `5xxx` — materials.
  - `6xxx` — voice / ASR.
  - `7xxx` — external integrations (RPA, payment provider, KYC).
  Each enum member carries a code string (e.g. `"4001"`), an HTTP status hint, and a default English `message_key` (i18n-friendly).
- **`BizException(HTTPException)`** — subclasses `HTTPException` so FastAPI's existing machinery still routes it; carries `code: ErrorCode` + optional `message` override + structured `details: dict`.
- **`build_error_payload(exc)`** — pure function that returns the canonical envelope:
  ```json
  {
    "ok": false,
    "code": "4001",
    "message": "Order not found",
    "message_key": "order.not_found",
    "details": { "order_id": "..." },
    "request_id": "..."
  }
  ```
- **`@app.exception_handler(BizException)`** in `main.py` converts every `BizException` to a `JSONResponse` with the correct HTTP status and the envelope above. No other code path emits `ok: false` directly.

Usage convention in services:

```python
raise BizException(ErrorCode.ORDER_NOT_FOUND, message="Order 42 not found")
raise BizException(ErrorCode.PAYMENT_SIGNATURE_INVALID,
                   details={"expected": expected, "got": got})
```

Non-`BizException` exceptions fall through to the default FastAPI handler (logged with `request_id` and surfaced as `code: SERVER_ERROR` with HTTP 500).

## Consequences

### Positive

- One exception type for the entire backend — service code reads uniformly (`raise BizException(...)`).
- Clients parse exactly one shape. The `code` field is the contract; the human-readable `message` and `message_key` are for display.
- Adding a new error is a one-line change in `ErrorCode` (or a new 8xxx block for a new domain). No router or handler edits needed.
- Tests can assert on the `code` field without coupling to message text.
- i18n integration is built in: clients receive `message_key` and look up the localized string via `vue-i18n` (web) or the mini-program equivalent.

### Negative / Trade-offs

- New contributors must learn the `ErrorCode` namespace and remember to raise `BizException` (not raw `HTTPException`). **Mitigation**: a Ruff rule (or pre-commit hook) flags `raise HTTPException` and a code-review checklist in `CONTRIBUTING.md`.
- The error envelope is opinionated — clients that assumed FastAPI's default 422 validation body must adapt. The migration is in `docs/API.md` (see the error-envelope section).
- `details` is `dict[str, Any]` and not formally typed; we accept this for now but a `TypedDict` per `ErrorCode` is on the backlog.

### Reversibility

Medium. The contract is shared with three clients, so changing the envelope is a coordinated migration. The enum + handler can be replaced in place, but clients will need a parallel adapter for one release.

## References

- `backend/app/core/errors.py` — `ErrorCode` enum + `BizException` + `build_error_payload`.
- `backend/app/main.py` — Global `@app.exception_handler(BizException)`.
- `docs/API.md` — Canonical error-envelope specification.
- All `app/api/v2/*.py` and `app/services/*.py` modules — usage examples (150+ `raise BizException(...)` sites).