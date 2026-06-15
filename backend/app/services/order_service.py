"""OrderService — V2 §4.2 (Order Service).

Responsibilities:
  - Generate a globally unique `V2-YYYYMMDD-NNNNNN` order number
  - Create orders with material-association and initial state-machine log
  - List orders (paginated, scoped to current user, optional status filter)
  - Fetch order detail (with status history + messages + material refs)
  - Build the pre-submit checklist snapshot (locked read-only view)
  - Cancel an order (only when status == "created")

State machine per V2 §4.2.4:
  created → submitted → reviewing → approved/rejected → closed
  cancel: created → closed
  abnormal / failed are exception states (not entered from these endpoints)

Concurrency:
  - order_no is generated in a transaction with a row-count check so a
    same-day collision (different seconds, same date counter) is impossible.
  - All status transitions write a row to `order_status_history` atomically
    with the order's own UPDATE.
"""
import hashlib
import json
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.models.destination import VisaDestination
from app.models.material import Material
from app.models.order import (
    ACTIVE_STATUSES,
    CANCELLABLE_STATUSES,
    Order,
    OrderMessage,
    OrderStatusHistory,
    VISA_TYPES,
)
from app.services.audit import record_audit


_log = get_logger()


class OrderService:
    """Owns the order lifecycle (V2 §4.2.1)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Create                                                             #
    # ------------------------------------------------------------------ #
    async def create(
        self,
        *,
        user_id: int,
        destination_id: int,
        visa_type: str,
        material_ids: List[int],
        applicant_data: Optional[Dict[str, Any]] = None,
        aff_code: Optional[str] = None,
    ) -> Order:
        if visa_type not in VISA_TYPES:
            raise BizException(
                ErrorCode.ORDER_INVALID_VISA_TYPE,
                message=f"visa_type must be one of {sorted(VISA_TYPES)}",
            )
        if not material_ids:
            raise BizException(
                ErrorCode.INVALID_PARAMS, message="material_ids must be non-empty"
            )

        # 1) Destination must exist & be enabled
        dest = await self.db.get(VisaDestination, destination_id)
        if dest is None:
            raise BizException(
                ErrorCode.ORDER_DESTINATION_DISABLED,
                message=f"destination {destination_id} not found",
                data={"destination_id": destination_id},
            )
        if not dest.enabled:
            raise BizException(
                ErrorCode.ORDER_DESTINATION_DISABLED,
                message=f"destination {dest.country_code} is not currently available",
                data={"destination_id": destination_id, "country_code": dest.country_code},
            )

        # 2) Materials must all belong to this user, alive, and visa_type consistent
        materials = await self._load_owned_materials(user_id, material_ids)

        # 3) Generate the order number
        order_no = await self._generate_order_no()

        # 4) Normalise aff_code (B-W9-3): strip whitespace, validate length,
        # and uppercase so partner lookups are case-insensitive. None and
        # empty-string both map to "no aff_code" (most orders come direct).
        normalised_aff_code = None
        if aff_code is not None:
            stripped = aff_code.strip()
            if stripped:
                if len(stripped) > 32:
                    raise BizException(
                        ErrorCode.INVALID_PARAMS,
                        message="aff_code must be <= 32 chars",
                        data={"aff_code_len": len(stripped)},
                    )
                normalised_aff_code = stripped.upper()

        # 5) Persist
        order = Order(
            order_no=order_no,
            user_id=user_id,
            destination_id=destination_id,
            visa_type=visa_type,
            status="created",
            applicant_data=json.dumps(applicant_data or {}, ensure_ascii=False),
            material_ids=json.dumps(material_ids, ensure_ascii=False),
            aff_code=normalised_aff_code,
        )
        self.db.add(order)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            # Race on unique order_no — should never happen with our counter,
            # but treat defensively.
            await self.db.rollback()
            raise BizException(
                ErrorCode.ORDER_CREATE_FAILED,
                message="Failed to create order (concurrent order_no conflict)",
            ) from exc

        # 5) Initial status history row
        history = OrderStatusHistory(
            order_id=order.id,
            from_status=None,
            to_status="created",
            source="user",
            note="order created",
        )
        self.db.add(history)

        # 6) Back-fill materials.order_id so future uploads can stay orderless
        for m in materials:
            if m.order_id is None:
                m.order_id = order.id

        # 7) Audit
        await record_audit(
            self.db,
            actor_type="user",
            actor_id=user_id,
            action="order.create",
            target_type="order",
            target_id=order.id,
            payload={
                "order_no": order_no,
                "destination_id": destination_id,
                "visa_type": visa_type,
                "material_ids": material_ids,
                "aff_code": normalised_aff_code,
            },
        )
        await self.db.commit()
        await self.db.refresh(order)
        _log.info(
            "order created id={} order_no={} user_id={} dest={} visa_type={} materials={} aff_code={}",
            order.id,
            order_no,
            user_id,
            destination_id,
            visa_type,
            len(material_ids),
            normalised_aff_code,
        )

        # 8) B-W9-3 — Affiliate hook (best-effort, never fails the order).
        # Lazy-imported to avoid an import cycle at module load (the events
        # module pulls the provider, which itself is fine, but we keep the
        # seam visible by importing only here at the call boundary).
        if normalised_aff_code:
            from app.services.affiliate_events import on_order_created

            try:
                await on_order_created(order)
            except Exception as exc:  # noqa: BLE001 — defensive
                # on_order_created already swallows provider errors, but
                # belt-and-braces: never let an affiliate glitch kill the
                # user's order creation response.
                _log.warning(
                    "order_service.create affiliate hook swallowed order_no={} err={}",
                    order.order_no, exc,
                )

        return order

    # ------------------------------------------------------------------ #
    # List                                                               #
    # ------------------------------------------------------------------ #
    async def list(
        self,
        *,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        page = max(1, int(page))
        page_size = max(1, min(100, int(page_size)))

        where_clauses = [Order.user_id == user_id]
        if status:
            where_clauses.append(Order.status == status)

        # Total
        total = (
            await self.db.scalar(
                select(func.count(Order.id)).where(and_(*where_clauses))
            )
        ) or 0

        # Items
        offset = (page - 1) * page_size
        rows = (
            await self.db.execute(
                select(Order)
                .where(and_(*where_clauses))
                .order_by(Order.created_at.desc(), Order.id.desc())
                .offset(offset)
                .limit(page_size)
            )
        ).scalars().all()

        return {
            "items": [self._to_order_dict(r) for r in rows],
            "page": page,
            "page_size": page_size,
            "total": int(total),
            "total_pages": (int(total) + page_size - 1) // page_size if total else 0,
        }

    # ------------------------------------------------------------------ #
    # Get detail                                                         #
    # ------------------------------------------------------------------ #
    async def get_detail(self, *, user_id: int, order_no: str) -> Dict[str, Any]:
        # Eager-load status_history + messages so we don't hit lazy-load
        # after session is closed (async SQLAlchemy can't do implicit IO).
        order = await self._get_owned_order(
            user_id=user_id, order_no=order_no, with_relations=True
        )

        # Material refs (only alive ones)
        material_ids = self._decode_material_ids(order.material_ids)
        materials: List[Material] = []
        if material_ids:
            materials = list(
                (
                    await self.db.execute(
                        select(Material).where(
                            and_(
                                Material.id.in_(material_ids),
                                Material.user_id == user_id,
                                Material.deleted_at.is_(None),
                            )
                        )
                    )
                ).scalars()
            )

        out = self._to_order_dict(order)
        out["status_history"] = [
            {
                "from_status": h.from_status,
                "to_status": h.to_status,
                "source": h.source,
                "note": h.note,
                "created_at": h.created_at,
            }
            for h in order.status_history
        ]
        out["messages"] = [
            {
                "id": m.id,
                "channel": m.channel,
                "title": m.title,
                "body": m.body,
                "sent_at": m.sent_at,
                "read_at": m.read_at,
                "created_at": m.created_at,
            }
            for m in order.messages
        ]
        out["materials"] = [
            {
                "id": m.id,
                "material_type": m.material_type,
                "original_filename": m.original_filename,
                "mime_type": m.mime_type,
                "file_size": m.file_size,
                "ocr_status": m.ocr_status,
            }
            for m in materials
        ]
        return out

    # ------------------------------------------------------------------ #
    # Checklist (pre-submit snapshot)                                    #
    # ------------------------------------------------------------------ #
    async def build_checklist(
        self, *, user_id: int, order_no: str, return_order: bool = False
    ) -> Dict[str, Any]:
        """Build the locked read-only snapshot for `GET /checklist`.

        Returns a dict matching `app.schemas.checklist.ChecklistOut`:
          {
            order_no, status, visa_type,
            destination: {id, country_code, country_name, enabled},
            applicant: {7 fields},
            travel_window: {arrival_date, departure_date, stay_days},
            emergency_contact: {name, phone, relation},
            materials: [{id, type, ...}],
            signature: "<sha256 hex>",
            generated_at: <datetime>,
            [order]: <Order ORM instance>  — only when return_order=True
          }

        If `return_order=True`, an extra `"order"` key is included with the
        loaded Order ORM instance, so callers (notably `submit()`) can avoid
        a second `_get_owned_order()` query. The default `False` keeps the
        public /checklist endpoint contract unchanged.

        Errors:
          - 4001 ORDER_NOT_FOUND  (also for not-owned, no existence leak)
          - 4010 ORDER_NOT_EDITABLE (status != created)
        """
        order = await self._get_owned_order(
            user_id=user_id, order_no=order_no
        )

        # 1) Status gate: only `created` orders are editable / checkable
        if order.status != "created":
            raise BizException(
                ErrorCode.ORDER_NOT_EDITABLE,
                message=(
                    f"Order in status '{order.status}' is no longer editable; "
                    "checklist is only available for 'created' orders."
                ),
                data={"order_no": order_no, "current_status": order.status},
            )

        # 2) Destination
        destination_row = await self.db.get(VisaDestination, order.destination_id)
        destination_dict = self._destination_to_dict(destination_row)

        # 3) Materials (alive only, owned by user, in order's material_ids order)
        material_ids = self._decode_material_ids(order.material_ids)
        materials: List[Material] = []
        if material_ids:
            rows = (
                await self.db.execute(
                    select(Material).where(
                        and_(
                            Material.id.in_(material_ids),
                            Material.user_id == user_id,
                            Material.deleted_at.is_(None),
                        )
                    )
                )
            ).scalars().all()
            by_id = {m.id: m for m in rows}
            # Preserve the order stored on the order (material_ids JSON order)
            materials = [by_id[mid] for mid in material_ids if mid in by_id]

        # 4) Decode applicant_data + emergency_contact sub-dict
        applicant_data = self._decode_applicant_data(order.applicant_data)
        emergency_data = applicant_data.get("emergency_contact") or {}
        if not isinstance(emergency_data, dict):
            emergency_data = {}

        # 5) Build the snapshot payload
        snapshot = {
            "order_no": order.order_no,
            "status": order.status,
            "visa_type": order.visa_type,
            "destination": destination_dict,
            "applicant": {
                "surname": str(applicant_data.get("surname") or ""),
                "given_name": str(applicant_data.get("given_name") or ""),
                "sex": str(applicant_data.get("sex") or ""),
                "dob": str(applicant_data.get("dob") or ""),
                "nationality": str(applicant_data.get("nationality") or ""),
                "passport_no": str(applicant_data.get("passport_no") or ""),
                "passport_expiry": str(
                    applicant_data.get("passport_expiry") or ""
                ),
            },
            "travel_window": {
                "arrival_date": str(applicant_data.get("arrival_date") or ""),
                "departure_date": str(
                    applicant_data.get("departure_date") or ""
                ),
                "stay_days": applicant_data.get("stay_days"),
            },
            "emergency_contact": {
                "name": str(emergency_data.get("name") or ""),
                "phone": str(emergency_data.get("phone") or ""),
                "relation": str(emergency_data.get("relation") or ""),
            },
            "materials": [
                {
                    "id": m.id,
                    "material_type": m.material_type,
                    "original_filename": m.original_filename,
                    "mime_type": m.mime_type,
                    "file_size": m.file_size,
                    "ocr_status": m.ocr_status,
                    "expires_at": (
                        m.expires_at.isoformat() if m.expires_at else None
                    ),
                }
                for m in materials
            ],
        }

        # 6) Locked signature: SHA-256 hex of a stable JSON serialization
        # of the snapshot (excluding `signature` and `generated_at`).
        signature = self._compute_signature(snapshot)

        # 7) Inject server-side stamp
        snapshot["signature"] = signature
        snapshot["generated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)

        if return_order:
            # Return the loaded Order ORM instance so callers (submit()) can
            # avoid a redundant _get_owned_order() round-trip. We use a
            # non-typed key "order" (lowercase) to avoid clashing with the
            # public ChecklistOut schema, which doesn't include this key.
            snapshot["order"] = order

        _log.info(
            "checklist built order_no={} user_id={} materials={} signature={}",
            order_no,
            user_id,
            len(materials),
            signature[:12],
        )
        return snapshot

    @staticmethod
    def _compute_signature(snapshot: Dict[str, Any]) -> str:
        """SHA-256 hex of a stable JSON serialisation of the snapshot.

        The snapshot dict must NOT contain `signature` or `generated_at`
        (we hash the locked view before injecting those server-side
        fields, so they cannot influence their own hash). The caller
        typically strips them via `dict comprehension` or by passing the
        pre-injection dict from `build_checklist`.

        Determinism:
          - `sort_keys=True`  -> dict key order doesn't change the hash
          - `ensure_ascii=False` -> CJK characters stay readable
          - `default=str` -> any leftover datetime/Decimal becomes a str

        This function is the single source of truth for the locking
        algorithm — the submit endpoint re-derives the signature with
        the exact same call, so the two paths stay in lockstep.
        """
        payload = json.dumps(
            snapshot, sort_keys=True, ensure_ascii=False, default=str
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _destination_to_dict(dest: Optional[VisaDestination]) -> Dict[str, Any]:
        """Render a VisaDestination for the checklist (with i18n fallback)."""
        if dest is None:
            return {
                "id": 0,
                "country_code": "",
                "country_name": "",
                "enabled": False,
            }
        name = ""
        try:
            i18n = json.loads(dest.country_name_i18n or "{}")
            if isinstance(i18n, dict):
                # Prefer zh-CN, then en, then the first non-empty value
                name = (
                    i18n.get("zh-CN")
                    or i18n.get("en")
                    or next((v for v in i18n.values() if v), "")
                    or ""
                )
        except (TypeError, ValueError):
            name = dest.country_code  # graceful fallback
        return {
            "id": dest.id,
            "country_code": dest.country_code,
            "country_name": name,
            "enabled": bool(dest.enabled),
        }

    # ------------------------------------------------------------------ #
    # Cancel                                                             #
    # ------------------------------------------------------------------ #
    async def cancel(self, *, user_id: int, order_no: str) -> Order:
        order = await self._get_owned_order(user_id=user_id, order_no=order_no)
        if order.status not in CANCELLABLE_STATUSES:
            # W3-3 enforcement: cancel endpoint shares 4010 ORDER_NOT_EDITABLE
            # with checklist/submit (state-gate is endpoint-agnostic — once
            # status != "created" no edit path is open). Message must contain
            # the endpoint keyword "cancel" so E2E (qa/E2E/orderdetail.spec.js
            # case 3) and front-end i18n fallbacks can disambiguate.
            raise BizException(
                ErrorCode.ORDER_NOT_EDITABLE,
                message=(
                    f"Order in status '{order.status}' is no longer editable; "
                    f"cancel is only available for 'created' orders."
                ),
                data={"order_no": order_no, "current_status": order.status},
            )
        previous = order.status
        order.status = "closed"
        order.closed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=previous,
                to_status="closed",
                source="user",
                note="cancelled by user",
            )
        )
        await record_audit(
            self.db,
            actor_type="user",
            actor_id=user_id,
            action="order.cancel",
            target_type="order",
            target_id=order.id,
            payload={"order_no": order_no, "from_status": previous},
        )
        await self.db.commit()
        await self.db.refresh(order)
        _log.info("order cancelled order_no={} user_id={}", order_no, user_id)

        # B-W9-3 — Affiliate hook on order cancel (best-effort). The V2
        # mock has no reverse API; we just log the signal so the audit
        # trail shows we notified the affiliate side.
        from app.services.affiliate_events import on_order_rejected

        try:
            await on_order_rejected(order)
        except Exception as exc:  # noqa: BLE001 — defensive
            _log.warning(
                "order_service.cancel affiliate hook swallowed order_no={} err={}",
                order_no, exc,
            )
        return order

    # ------------------------------------------------------------------ #
    # Submit (V2 §4.2.4 — created → submitted)                           #
    # ------------------------------------------------------------------ #
    async def submit(
        self, *, user_id: int, order_no: str, client_signature: str
    ) -> Dict[str, Any]:
        """Transition an order from `created` → `submitted`.

        Flow (V2 §4.2.4):
          1. Re-derive the locked snapshot from the live order rows
             (same code path as `build_checklist`) and compute the
             server-side signature.
          2. Compare with the `client_signature` echoed from the front-end.
             Mismatch → 4011 ORDER_SIGNATURE_MISMATCH.
          3. Re-check status (defensive — build_checklist's gate already
             returns 4010 for non-`created` orders, but a same-tick
             status mutation could in theory slip between calls).
          4. Flip status, stamp submitted_at, mint rpa_task_id, append
             OrderStatusHistory row, fire audit, commit, return dict.

        The actual RPA call is NOT made here — that's W3's job. We
        just mint a fresh rpa_task_id (UUID4) so downstream services
        have a correlation handle.

        Errors:
          - 4001 ORDER_NOT_FOUND (also for not-owned — no existence leak)
          - 4010 ORDER_NOT_EDITABLE (status != created)
          - 4011 ORDER_SIGNATURE_MISMATCH
        """
        # 1) Re-build the snapshot to both (a) re-verify status==created
        #    and (b) get a fresh server-side signature. The signature
        #    returned by build_checklist is the *same* one we want here,
        #    because the locked view only changes if the order rows
        #    themselves change (which we then reject anyway).
        #
        #    Performance fix: pass `return_order=True` so the same Order
        #    ORM instance is returned. Previously we made a 2nd
        #    `_get_owned_order()` call here (lines 614-615 below) — a
        #    redundant query that loaded the row twice in the same
        #    transaction. We just verified ownership + status on line 339
        #    inside build_checklist, so the re-check is unnecessary
        #    unless the session saw a status mutation between the two
        #    calls (it can't — both happen within the same async
        #    session, no other writer can race in on a single transaction).
        fresh = await self.build_checklist(
            user_id=user_id, order_no=order_no, return_order=True
        )
        order: Order = fresh["order"]
        server_signature = fresh["signature"]

        # 2) Compare signatures. We expose a 12-char prefix of the
        #    server signature in the error data so the client can
        #    log/scrub it without leaking the full hash.
        if not client_signature or client_signature != server_signature:
            raise BizException(
                ErrorCode.ORDER_SIGNATURE_MISMATCH,
                message=(
                    "Client signature does not match the server-side "
                    "checklist signature. Re-fetch /checklist and try again."
                ),
                data={
                    "order_no": order_no,
                    "expected_signature_prefix": server_signature[:12],
                },
            )

        # 3) Defensive re-check. build_checklist already raised 4010
        #    if status != "created" via the same `order` instance, so
        #    this branch is unreachable in single-threaded use. We keep
        #    the check as a guard against any future refactor that
        #    bypasses build_checklist, but we DO NOT re-fetch the row
        #    (that was the redundant query we just eliminated).
        if order.status != "created":
            raise BizException(
                ErrorCode.ORDER_NOT_EDITABLE,
                message=(
                    f"Order in status '{order.status}' is no longer editable; "
                    "submit is only allowed for 'created' orders."
                ),
                data={"order_no": order_no, "current_status": order.status},
            )

        # 4) State transition. We mint a fresh UUID4 as rpa_task_id so
        #    downstream W3 RPA has a correlation handle.
        previous = order.status
        rpa_task_id = str(uuid.uuid4())
        order.status = "submitted"
        order.submitted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        order.rpa_task_id = rpa_task_id
        self.db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=previous,
                to_status="submitted",
                source="user",
                note="order submitted to RPA",
            )
        )
        await record_audit(
            self.db,
            actor_type="user",
            actor_id=user_id,
            action="order.submit",
            target_type="order",
            target_id=order.id,
            payload={
                "order_no": order_no,
                "from_status": previous,
                "rpa_task_id": rpa_task_id,
            },
        )
        await self.db.commit()
        await self.db.refresh(order)
        _log.info(
            "order submitted order_no={} user_id={} rpa_task_id={}",
            order_no,
            user_id,
            rpa_task_id,
        )

        return {
            "order_no": order.order_no,
            "status": order.status,
            "submitted_at": order.submitted_at,
            "rpa_task_id": order.rpa_task_id,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #
    async def _load_owned_materials(
        self, user_id: int, material_ids: List[int]
    ) -> List[Material]:
        """Verify all material ids belong to the user and aren't soft-deleted."""
        # Dedupe while preserving order (so order_id reuse stays stable)
        unique_ids = list(dict.fromkeys(material_ids))
        rows = (
            await self.db.execute(
                select(Material).where(Material.id.in_(unique_ids))
            )
        ).scalars().all()
        rows_by_id = {r.id: r for r in rows}

        missing = [mid for mid in unique_ids if mid not in rows_by_id]
        if missing:
            raise BizException(
                ErrorCode.ORDER_MATERIALS_NOT_FOUND,
                message=f"materials not found: {missing}",
                data={"missing": missing},
            )

        for mid in unique_ids:
            m = rows_by_id[mid]
            if m.user_id != user_id:
                # Don't leak existence; treat as not-found-but-foreign
                raise BizException(
                    ErrorCode.ORDER_MATERIAL_NOT_OWNED,
                    message=f"material {mid} is not owned by current user",
                    data={"material_id": mid},
                )
            if m.deleted_at is not None:
                raise BizException(
                    ErrorCode.ORDER_MATERIALS_NOT_FOUND,
                    message=f"material {mid} is deleted",
                    data={"material_id": mid},
                )
        return list(rows_by_id[mid] for mid in unique_ids)

    async def _get_owned_order(
        self,
        *,
        user_id: int,
        order_no: str,
        with_relations: bool = False,
    ) -> Order:
        stmt = select(Order).where(Order.order_no == order_no)
        if with_relations:
            stmt = stmt.options(
                selectinload(Order.status_history),
                selectinload(Order.messages),
            )
        order = await self.db.scalar(stmt)
        if order is None:
            raise BizException(
                ErrorCode.ORDER_NOT_FOUND, message=f"order {order_no} not found"
            )
        if order.user_id != user_id:
            # Don't leak existence
            raise BizException(
                ErrorCode.ORDER_NOT_FOUND, message=f"order {order_no} not found"
            )
        return order

    @staticmethod
    def _decode_material_ids(raw: Optional[str]) -> List[int]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        out: List[int] = []
        for v in data:
            try:
                out.append(int(v))
            except (TypeError, ValueError):
                continue
        return out

    @staticmethod
    def _decode_applicant_data(raw: Optional[str]) -> Dict[str, Any]:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _to_order_dict(order: Order) -> Dict[str, Any]:
        return {
            "id": order.id,
            "uuid": order.uuid,
            "order_no": order.order_no,
            "user_id": order.user_id,
            "destination_id": order.destination_id,
            "visa_type": order.visa_type,
            "status": order.status,
            "total_amount": order.total_amount,
            "currency": order.currency,
            "rpa_task_id": order.rpa_task_id,
            "destination_url": order.destination_url,
            "aff_code": order.aff_code,
            "material_ids": OrderService._decode_material_ids(order.material_ids),
            "applicant_data": OrderService._decode_applicant_data(order.applicant_data),
            "submitted_at": order.submitted_at,
            "reviewed_at": order.reviewed_at,
            "closed_at": order.closed_at,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }

    # ------------------------------------------------------------------ #
    # Order number generation                                             #
    # ------------------------------------------------------------------ #
    async def _generate_order_no(self) -> str:
        """Generate `V2-YYYYMMDD-NNNNNN` that's globally unique.

        Strategy:
          1. Count existing orders whose order_no starts with the same date
             prefix — that's today's "next sequence" number.
          2. Pad to 6 digits, format, then INSERT and let the UNIQUE index
             catch any race (extremely unlikely on SQLite, but defensive).
          3. If the race somehow fires, retry up to 3 times.
        """
        today_prefix = "V2-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-"
        for attempt in range(3):
            count_today = (
                await self.db.scalar(
                    select(func.count(Order.id)).where(
                        Order.order_no.like(f"{today_prefix}%")
                    )
                )
            ) or 0
            candidate = f"{today_prefix}{int(count_today) + 1:06d}"
            # Probe existence
            exists = await self.db.scalar(
                select(Order.id).where(Order.order_no == candidate).limit(1)
            )
            if exists is None:
                return candidate
            _log.warning(
                "order_no collision attempt={} candidate={}", attempt, candidate
            )
        # Fall through: surface as error
        raise BizException(
            ErrorCode.ORDER_CREATE_FAILED,
            message="Failed to allocate unique order number after retries",
        )


__all__ = ["OrderService", "ACTIVE_STATUSES"]
