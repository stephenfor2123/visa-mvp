# ADR-0001: Backend framework — FastAPI (not Django)

- **Status**: Accepted
- **Date**: 2026-06-15
- **Scope**: Backend service (`backend/app/`)

## Context

The visa MVP backend needs to expose a JSON-only REST API consumed by three clients (web, iOS, mini-program). Workloads are heavily I/O-bound:

- SMS / email dispatch (network round-trips, 1–5 s latency).
- Material upload via signed URLs to S3-compatible storage.
- RPA submission to upstream visa portals (long-running, eventually consistent).
- WebSocket push for order state transitions (`ws_orders.py`).
- Admin dashboard queries across joined tables.

We evaluated two mainstream Python web frameworks.

### Option A — Django + Django REST Framework

- Mature, batteries-included (ORM, admin, auth, migrations).
- Synchronous WSGI request cycle; async support exists but is opt-in and uneven across third-party packages.
- DRF's serializer / viewset model is verbose for a thin API that mostly proxies business services.
- Channels add operational complexity (separate worker, ASGI bridge) for the WebSocket surface we need.

### Option B — FastAPI

- ASGI-native, built on Starlette + `uvicorn`; `async def` endpoints are the default, sync code is auto-offloaded to a threadpool.
- Pydantic v2 type-annotated request/response models — the same models double as OpenAPI schema.
- First-class `WebSocket` route support, no separate Channels-like infrastructure.
- Dependency injection (`Depends`) cleanly expresses auth, DB session, rate-limit middleware.
- Async ecosystem (`httpx`, `asyncpg`, `aiosqlite`, `python-telegram-bot`-style libraries) is mature enough for our external integrations.

### Option C — Flask + flask-smorest

- Familiar sync-first model; async is third-party. Lighter than Django but heavier than FastAPI for OpenAPI generation. Considered but not chosen — does not pull its weight relative to FastAPI for this workload.

## Decision

We adopt **FastAPI 0.110+** for the backend.

- Endpoints are `async def` whenever they await external I/O (SMS, RPA, S3, payment provider).
- Pydantic v2 schemas live next to the service layer they validate; OpenAPI is auto-generated and consumed by the frontend team for typed client wrappers.
- SQLAlchemy 2.x is used in async mode (`AsyncSession`) for DB access; the existing `visa.db` migrations were converted from Alembic single-head to async-compatible.
- WebSockets use FastAPI's built-in `WebSocket` route (`ws_orders.py`), no Channels / extra worker.
- Django is **not** introduced as a side framework — admin is implemented in the Vue SPA (`frontend/web/src/views/admin/*`) hitting the same `/api/v2/admin/*` routes.

## Consequences

### Positive

- Single async-first execution model across HTTP, WebSocket, and external calls. No sync/async impedance mismatch.
- Auto-generated OpenAPI at `/docs` and `/openapi.json` — frontend uses it to generate TS types.
- Pydantic validation surfaces at the route boundary; bad requests fail with a structured `422` body referencing the field path.
- WebSocket routing is one decorator (`@app.websocket(...)`) — no extra process to operate.

### Negative / Trade-offs

- FastAPI is younger than Django; some enterprise integrations (LDAP, certain government SSO stacks) ship Django middleware first. We'll wrap them in `app/integrations/` as needed.
- Pydantic v2 upgrade from v1 required rewriting some `validator` decorators — a one-time cost.
- `BackgroundTasks` in FastAPI is in-process; for the RPA workload we use Celery / `arq` separately to survive restarts (out of scope for this ADR).

### Reversibility

Low–medium. Migrating to Django would require rewriting routing, request validation, and DI — but the service layer (`app/services/`) and DB models are framework-agnostic and would survive. Estimated effort: 2–3 sprints.

## References

- `backend/app/main.py` — FastAPI app, exception handlers, lifespan.
- `backend/app/core/errors.py` — Pydantic-friendly error envelope.
- `backend/app/api/v2/` — Versioned route modules.
- `backend/app/api/v2/ws_orders.py` — Built-in WebSocket route.