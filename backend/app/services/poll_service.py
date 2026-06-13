"""PollService — V2 §4.2.4 (state machine) + §4.3 RPA handoff.

Owns the periodic poll-tick loop that walks in-flight orders, asks the
RPA system "what's new?", and writes the outcome to:

  * `order_poll_log`  (audit trail, one row per actual state change)
  * `orders.status`   (the order's current state)
  * `order_status_history` (the same append-only log the API writes)

The RPA itself is stubbed in `_rpa_stub()` for the MVP — it returns a
deterministic-ish state transition so the UI / ETag flow can be exercised
end-to-end. Swapping in a real vendor (Playwright, BrowserUse, ...) is a
single-method replacement later.

Why a separate `record_change()` method
---------------------------------------
The RPA vendor can also **push** status updates via webhook instead of
waiting for us to poll. Both flows share the same persistence rules,
so we expose `record_change()` as the canonical "write one transition"
primitive; the periodic `tick()` is just a fan-out of that primitive.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.order import Order, OrderStatusHistory
from app.models.order_poll_log import POLL_SOURCES, OrderPollLog

# W3 cycle 3: fan out committed status changes to live WS subscribers.
# Imported lazily inside record_change() to avoid a hard cycle at module
# import time (ws_orders imports app.core.security which is fine, but
# keeping the import here keeps the data path explicit).
async def _broadcast_to_ws_subscribers(
    order_no: str,
    *,
    status_after: str,
    status_before: Optional[str],
    poll_source: str,
    polled_at: "datetime",
) -> None:
    """Fire-and-forget WS push to every subscriber of `order_no`.

    Uses asyncio.create_task so the synchronous return path of
    record_change() is not blocked. Failures inside broadcast()
    are already caught by ConnectionManager and logged, so we
    don't add a done-callback here — it's an at-most-once signal.
    """
    import asyncio

    from app.api.v2.ws_orders import connection_manager

    payload = {
        "type": "status",
        "data": {
            "order_no": order_no,
            "status": status_after,
            "status_before": status_before,
            "poll_source": poll_source,
            "polled_at": polled_at.isoformat() if polled_at else None,
        },
    }
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop (e.g. called from sync code in a worker thread
        # outside an async context). Skip — there's no WS to push to.
        return
    loop.create_task(connection_manager.broadcast(order_no, payload))


_log = get_logger()


# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #
# Statuses we actively poll for. Anything terminal (approved / rejected /
# closed / abnormal / failed) is skipped — once a vendor tells us "done"
# we don't re-prompt them.
POLLABLE_STATUSES: tuple[str, ...] = ("submitted", "reviewing")

# Forward-only transitions emitted by the stub.
# Real RPA will eventually return whatever it actually saw on the gov
# portal; the stub models the most common happy path + one failure.
_STUB_TRANSITIONS: dict[str, dict[str, float]] = {
    # From "submitted": 50% advance to reviewing, 10% rejected
    "submitted": {
        "reviewing": 0.50,
        "rejected": 0.10,
    },
    # From "reviewing": 30% advance to approved, 10% rejected
    "reviewing": {
        "approved": 0.30,
        "rejected": 0.10,
    },
}


class PollService:
    """Bulk + single-shot order status polling."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Bulk tick                                                          #
    # ------------------------------------------------------------------ #
    async def tick(
        self,
        *,
        poll_source: str = "scheduler_tick",
        rng: Optional[random.Random] = None,
        notes_prefix: Optional[str] = None,
    ) -> dict[str, Any]:
        """Walk all POLLABLE_STATUSES orders and ask RPA for an update.

        Returns:
            {
                "ticked":  <int>  number of orders inspected,
                "changed": <int>  number that actually moved to a new status,
                "logs":    <list[dict]>  one entry per state change,
            }

        Notes:
            * `rng` parameter is injected for tests so we can pin the random
              roll to a deterministic value. Defaults to a fresh
              `random.Random()` instance (process-local seed).
            * The tick commits a single transaction at the end. If any
              one-row update fails, the whole batch rolls back.
        """
        if poll_source not in POLL_SOURCES:
            raise ValueError(
                f"poll_source must be one of {list(POLL_SOURCES)}, got {poll_source!r}"
            )

        rng = rng or random.Random()

        # 1) Fetch pollable orders. Locked via row-id so a concurrent
        # /scheduler/poll-tick from another worker waits for us. SQLite
        # serialises writes anyway, but the explicit BEGIN IMMEDIATE
        # pattern keeps the contract portable.
        rows = (
            await self.db.execute(
                select(Order)
                .where(Order.status.in_(POLLABLE_STATUSES))
                .order_by(Order.id.asc())
            )
        ).scalars().all()

        ticked = 0
        changed = 0
        logs: list[dict[str, Any]] = []

        for order in rows:
            ticked += 1
            polled_at = datetime.now(timezone.utc).replace(tzinfo=None)
            status_before = order.status

            # Ask the RPA (stub) what the new state should be.
            new_status = self._rpa_stub(status_before, rng=rng)

            if new_status == status_before:
                # No transition — per task spec, do NOT write a log row.
                # We still increment `ticked` so the count reflects work done.
                _log.debug(
                    "poll no-change order_no={} status={} src={}",
                    order.order_no,
                    status_before,
                    poll_source,
                )
                continue

            # 2) Persist state change
            changed += 1
            notes = self._compose_notes(
                notes_prefix=notes_prefix,
                poll_source=poll_source,
                status_before=status_before,
                status_after=new_status,
            )
            log_row = await self.record_change(
                order=order,
                status_before=status_before,
                status_after=new_status,
                poll_source=poll_source,
                polled_at=polled_at,
                notes=notes,
                commit=False,  # batch commit at end
            )
            logs.append(self._log_to_dict(log_row))

        # 3) Single commit for the whole batch
        if changed > 0:
            await self.db.commit()

        _log.info(
            "poll-tick src={} ticked={} changed={}", poll_source, ticked, changed
        )
        return {"ticked": ticked, "changed": changed, "logs": logs}

    # ------------------------------------------------------------------ #
    # Single-row record (also used by RPA webhook callback)              #
    # ------------------------------------------------------------------ #
    async def record_change(
        self,
        *,
        order: Order,
        status_before: Optional[str],
        status_after: str,
        poll_source: str,
        polled_at: Optional[datetime] = None,
        notes: Optional[str] = None,
        commit: bool = True,
    ) -> OrderPollLog:
        """Persist one state transition: order row + history + poll log.

        `commit` defaults to True for the webhook path; the bulk tick
        passes `commit=False` and commits once at the end of the batch.

        Raises:
            ValueError: if `poll_source` is not in `POLL_SOURCES` or
                        `status_after` is empty.
        """
        if poll_source not in POLL_SOURCES:
            raise ValueError(
                f"poll_source must be one of {list(POLL_SOURCES)}, got {poll_source!r}"
            )
        if not status_after:
            raise ValueError("status_after must be non-empty")

        polled_at = polled_at or datetime.now(timezone.utc).replace(tzinfo=None)

        # 1) Mutate the order
        order.status = status_after
        # Stamp the relevant transition timestamp
        if status_after == "reviewing":
            order.reviewed_at = polled_at
        elif status_after in ("approved", "rejected"):
            order.reviewed_at = order.reviewed_at or polled_at
        elif status_after in ("closed", "abnormal", "failed"):
            order.closed_at = polled_at

        self.db.add(order)

        # 2) Append-only history row (same table the user-facing API writes)
        self.db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=status_before,
                to_status=status_after,
                source="scheduler" if poll_source == "scheduler_tick" else "rpa",
                note=notes or f"poll ({poll_source})",
            )
        )

        # 3) Poll audit row
        log_row = OrderPollLog(
            order_no=order.order_no,
            polled_at=polled_at,
            status_before=status_before,
            status_after=status_after,
            poll_source=poll_source,
            notes=notes,
        )
        self.db.add(log_row)
        await self.db.flush()  # populate log_row.id + assigned timestamps

        if commit:
            await self.db.commit()
            await self.db.refresh(log_row)

        # W3 cycle 3: fan out to live WS subscribers. Always run (not
        # gated on `commit`) so the bulk-tick path also pushes; the
        # DB state is already flushed and the batch commit at the end
        # of tick() is the durable boundary.
        await _broadcast_to_ws_subscribers(
            order.order_no,
            status_after=status_after,
            status_before=status_before,
            poll_source=poll_source,
            polled_at=polled_at,
        )

        _log.info(
            "poll change order_no={} {}→{} src={}",
            order.order_no,
            status_before,
            status_after,
            poll_source,
        )
        return log_row

    # ------------------------------------------------------------------ #
    # Audit query (used by /orders/{no}/poll-history, future)            #
    # ------------------------------------------------------------------ #
    async def history_for(self, order_no: str) -> list[OrderPollLog]:
        """Return all poll-log rows for one order, oldest-first."""
        rows = (
            await self.db.execute(
                select(OrderPollLog)
                .where(OrderPollLog.order_no == order_no)
                .order_by(OrderPollLog.polled_at.asc(), OrderPollLog.id.asc())
            )
        ).scalars().all()
        return list(rows)

    # ------------------------------------------------------------------ #
    # RPA stub                                                            #
    # ------------------------------------------------------------------ #
    def _rpa_stub(
        self, current_status: str, *, rng: random.Random
    ) -> str:
        """Return what RPA would report back for `current_status`.

        Stub rules (per Story spec):
          - from `submitted`:  50% → reviewing, 10% → rejected, else stay
          - from `reviewing`:  30% → approved, 10% → rejected, else stay

        Other statuses are unreachable through tick() because the WHERE
        clause filters to POLLABLE_STATUSES; defensive return = same.
        """
        rules = _STUB_TRANSITIONS.get(current_status)
        if not rules:
            return current_status

        roll = rng.random()
        cumulative = 0.0
        for target, prob in rules.items():
            cumulative += prob
            if roll < cumulative:
                return target
        return current_status

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _compose_notes(
        *,
        notes_prefix: Optional[str],
        poll_source: str,
        status_before: Optional[str],
        status_after: str,
    ) -> str:
        bits: list[str] = []
        if notes_prefix:
            bits.append(notes_prefix)
        bits.append(f"{poll_source}")
        bits.append(f"{status_before}→{status_after}")
        return " | ".join(bits)

    @staticmethod
    def _log_to_dict(row: OrderPollLog) -> dict[str, Any]:
        return {
            "id": row.id,
            "order_no": row.order_no,
            "polled_at": row.polled_at,
            "status_before": row.status_before,
            "status_after": row.status_after,
            "poll_source": row.poll_source,
            "notes": row.notes,
        }


__all__ = ["PollService", "POLLABLE_STATUSES"]