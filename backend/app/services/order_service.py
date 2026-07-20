"""OrderService — V2 §4.2 (Order Service).

Responsibilities:
  - Generate a globally unique `V2-YYYYMMDD-XXXXXXXX` order number
    (uuid4 short hex suffix — 32-bit space gives 1-in-4B collision odds,
     so race-free under any realistic concurrent load; the previous
     count-then-insert counter could lose orders under 10+ concurrent
     creates per the same date prefix).
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
  - order_no suffix uses uuid4 short hex (8 chars, 32-bit uniqueness)
    instead of a per-day sequence counter, eliminating read-then-insert
    races under concurrent order creation.
  - All status transitions write a row to `order_status_history` atomically
    with the order's own UPDATE.
"""
import hashlib
import json
import uuid
from collections.abc import Iterable

from app.core.product_scope import is_allowed_destination, normalize_destination_code
from decimal import Decimal
from datetime import datetime, timedelta, timezone
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
    ORDER_LOCK_SECONDS,
    PORTAL_SUBMIT_SOURCES,
    REFUND_STATUSES,
    Order,
    OrderMessage,
    OrderStatusHistory,
    VISA_TYPES,
)
from app.services.audit import record_audit
from app.services.pricing_service import PricingService


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
        # Product scope guard — refuse ID/VN/JP/… even if a row was re-enabled in admin
        if not is_allowed_destination(dest.country_code):
            raise BizException(
                ErrorCode.ORDER_DESTINATION_DISABLED,
                message=(
                    f"destination {normalize_destination_code(dest.country_code)} "
                    "is outside product scope (US / GB / AU / Schengen only)"
                ),
                data={
                    "destination_id": destination_id,
                    "country_code": dest.country_code,
                },
            )

        # 2) Legacy material association (optional — privacy-first flow uses applicant_data only)
        materials = []
        if material_ids:
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

        # Platform service fee snapshot at order creation (not consular/visa_fee_usd).
        pricing = await PricingService(self.db).get_current()
        order_total_usd = Decimal(str(pricing["display_price_usd"]))
        order_currency = "USD"

        # A-01: unpaid (created) orders must NOT persist applicant PII.
        # Client may still send applicant_data for local UX; it is discarded here.
        # Full profile is attached only after payment via set_applicant_data.
        _ = applicant_data
        order = Order(
            order_no=order_no,
            user_id=user_id,
            destination_id=destination_id,
            visa_type=visa_type,
            status="created",
            total_amount=order_total_usd,
            currency=order_currency,
            applicant_data=None,
            material_ids=json.dumps(material_ids, ensure_ascii=False),
            aff_code=normalised_aff_code,
            locked_until=self._utcnow() + timedelta(seconds=ORDER_LOCK_SECONDS),
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

        # 6) Back-fill materials.order_id (legacy path only)
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
                "service_fee_usd": str(order_total_usd),
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
            except Exception as exc:  # pragma: no cover
                _log.warning("affiliate on_order_created failed: {}", exc)

        return order

    # Statuses that may hold applicant PII on the server (post-payment only).
    _APPLICANT_ATTACH_STATUSES = frozenset({
        "paid", "completed", "submitted", "reviewing", "approved",
    })

    async def set_applicant_data(
        self,
        *,
        user_id: int,
        order_no: str,
        applicant_data: Dict[str, Any],
    ) -> Order:
        """Attach full applicant profile after payment (A-01 gate)."""
        order = await self._get_owned_order(user_id, order_no)
        if order.status not in self._APPLICANT_ATTACH_STATUSES:
            raise BizException(
                ErrorCode.ORDER_INVALID_STATE,
                message="Applicant data can only be attached after payment",
                data={"status": order.status},
            )
        if not isinstance(applicant_data, dict) or not applicant_data:
            raise BizException(
                ErrorCode.INVALID_PARAMS,
                message="applicant_data must be a non-empty object",
            )
        order.applicant_data = json.dumps(applicant_data, ensure_ascii=False)
        # Profile change invalidates any outstanding plugin code.
        from app.core.ds160 import revoke_order_ds160
        revoke_order_ds160(order)
        await record_audit(
            self.db,
            actor_type="user",
            actor_id=user_id,
            action="order.applicant_data.set",
            target_type="order",
            target_id=order.id,
            payload={"order_no": order_no, "field_count": len(applicant_data)},
        )
        await self.db.commit()
        await self.db.refresh(order)
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

        # Bulk-load destination rows so the list endpoint doesn't N+1.
        # We map destination_id -> dict once, then attach per order.
        dest_ids = {r.destination_id for r in rows if r.destination_id}
        dest_by_id: dict[int, VisaDestination] = {}
        if dest_ids:
            dest_rows = (
                await self.db.execute(
                    select(VisaDestination).where(VisaDestination.id.in_(dest_ids))
                )
            ).scalars().all()
            dest_by_id = {d.id: d for d in dest_rows}

        return {
            "items": [
                self._to_order_dict(r, dest=dest_by_id.get(r.destination_id))
                for r in rows
            ],
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
        await self.maybe_expire_order(order)

        # Destination (eager-load to avoid lazy-load after session close;
        # _to_order_dict expects the ORM row, see list_orders at L249-256
        # for the same pattern).
        destination_row = await self.db.get(VisaDestination, order.destination_id)

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

        out = self._to_order_dict(order, dest=destination_row)
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
    def _destination_display_name(dest: VisaDestination) -> str:
        """Best-effort display name from country_name_i18n, fallback to code."""
        if dest is None:
            return ""
        try:
            i18n = json.loads(dest.country_name_i18n or "{}")
            if isinstance(i18n, dict):
                name = (
                    i18n.get("zh-CN")
                    or i18n.get("en")
                    or next((v for v in i18n.values() if v), "")
                    or ""
                )
                if name:
                    return name
        except (TypeError, ValueError):
            pass
        return dest.country_code or ""

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
        name = OrderService._destination_display_name(dest) or dest.country_code
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
        await self.maybe_expire_order(order)
        if order.status != "created":
            raise BizException(
                ErrorCode.ORDER_NOT_EDITABLE,
                message=(
                    f"Order in status '{order.status}' is no longer editable; "
                    f"cancel is only available for 'created' orders."
                ),
                data={"order_no": order_no, "current_status": order.status},
            )
        order.status = "cancelled"
        order.closed_at = self._utcnow()
        self.db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=previous,
                to_status="cancelled",
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
    # Lifecycle v2 — expire / diagnosis / portal / refund                #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    async def maybe_expire_order(self, order: Order, *, commit: bool = True) -> bool:
        """Auto-cancel unpaid orders past locked_until. Returns True if expired."""
        if order.status != "created" or not order.locked_until:
            return False
        if self._utcnow() <= order.locked_until:
            return False
        prev = order.status
        order.status = "cancelled"
        order.closed_at = self._utcnow()
        self.db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=prev,
                to_status="cancelled",
                source="scheduler",
                note="payment lock expired (1h)",
            )
        )
        if commit:
            await self.db.commit()
            await self.db.refresh(order)
        return True

    async def complete_diagnosis(self, *, user_id: int, order_no: str) -> Order:
        """AI diagnosis finished → order service complete (paid → completed)."""
        order = await self._get_owned_order(user_id=user_id, order_no=order_no)
        if order.status == "completed":
            return order
        if order.status != "paid":
            raise BizException(
                ErrorCode.ORDER_NOT_EDITABLE,
                message=f"Diagnosis completion requires status 'paid', got '{order.status}'",
                data={"order_no": order_no, "current_status": order.status},
            )
        now = self._utcnow()
        prev = order.status
        order.status = "completed"
        order.diagnosis_completed_at = now
        order.completed_at = now
        self.db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=prev,
                to_status="completed",
                source="user",
                note="AI diagnosis completed",
            )
        )
        await record_audit(
            self.db,
            actor_type="user",
            actor_id=user_id,
            action="order.diagnosis.complete",
            target_type="order",
            target_id=order.id,
            payload={"order_no": order_no},
        )
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def mark_portal_submitted(
        self,
        *,
        user_id: int,
        order_no: str,
        source: str = "user",
    ) -> Order:
        """Milestone only — does not change order.status."""
        if source not in PORTAL_SUBMIT_SOURCES:
            raise BizException(
                ErrorCode.INVALID_PARAMS,
                message=f"source must be one of {PORTAL_SUBMIT_SOURCES}",
            )
        order = await self._get_owned_order(user_id=user_id, order_no=order_no)
        if order.status not in ("paid", "completed") and order.status not in (
            "submitted", "reviewing", "approved",
        ):
            raise BizException(
                ErrorCode.ORDER_NOT_EDITABLE,
                message="Portal submission can only be recorded after payment",
                data={"order_no": order_no, "current_status": order.status},
            )
        now = self._utcnow()
        if order.portal_submitted_at is None:
            order.portal_submitted_at = now
            order.portal_submitted_source = source
            if order.ds160_portal_submitted_at is None:
                order.ds160_portal_submitted_at = now
        await record_audit(
            self.db,
            actor_type="user" if source == "user" else "system",
            actor_id=user_id if source == "user" else 0,
            action="order.portal.submitted",
            target_type="order",
            target_id=order.id,
            payload={"order_no": order_no, "source": source},
        )
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def request_refund(
        self,
        *,
        user_id: int,
        order_no: str,
        reason: str,
        amount: Optional[Decimal] = None,
    ) -> Order:
        order = await self._get_owned_order(user_id=user_id, order_no=order_no)
        if order.status not in ("paid", "completed") and order.status not in (
            "submitted", "reviewing", "approved",
        ):
            raise BizException(
                ErrorCode.ORDER_NOT_EDITABLE,
                message="Refund only available for paid/completed orders",
            )
        if (order.refund_status or "none") not in ("none", "rejected", "failed"):
            raise BizException(
                ErrorCode.ORDER_NOT_EDITABLE,
                message=f"Refund already in progress: {order.refund_status}",
            )
        order.refund_status = "pending"
        order.refund_reason = (reason or "").strip()[:2000] or None
        order.refund_amount = amount if amount is not None else order.total_amount
        order.refund_requested_at = self._utcnow()
        await record_audit(
            self.db,
            actor_type="user",
            actor_id=user_id,
            action="order.refund.request",
            target_type="order",
            target_id=order.id,
            payload={"order_no": order_no, "amount": str(order.refund_amount)},
        )
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def get_attention_counts(self) -> Dict[str, int]:
        """Ops dashboard: orders needing follow-up."""
        now = self._utcnow()
        soon = now + timedelta(minutes=15)
        q_pay_soon = select(func.count()).select_from(Order).where(
            and_(Order.status == "created", Order.locked_until.isnot(None), Order.locked_until <= soon, Order.locked_until > now)
        )
        q_paid_no_diag = select(func.count()).select_from(Order).where(
            and_(Order.status == "paid", Order.diagnosis_completed_at.is_(None))
        )
        q_completed_no_portal = select(func.count()).select_from(Order).where(
            and_(Order.status == "completed", Order.portal_submitted_at.is_(None))
        )
        q_refund_pending = select(func.count()).select_from(Order).where(
            Order.refund_status == "pending"
        )
        q_refund_failed = select(func.count()).select_from(Order).where(
            Order.refund_status == "failed"
        )
        return {
            "payment_expiring_soon": (await self.db.scalar(q_pay_soon)) or 0,
            "paid_awaiting_diagnosis": (await self.db.scalar(q_paid_no_diag)) or 0,
            "completed_awaiting_portal": (await self.db.scalar(q_completed_no_portal)) or 0,
            "refund_pending": (await self.db.scalar(q_refund_pending)) or 0,
            "refund_failed": (await self.db.scalar(q_refund_failed)) or 0,
        }

    # ------------------------------------------------------------------ #
    # Delete draft (W67)                                                  #
    # ------------------------------------------------------------------ #
    async def delete_draft(self, *, user_id: int, order_no: str) -> Dict[str, Any]:
        """Hard-delete a draft order + soft-delete its associated materials.

        Scope: only `status == "created"` orders (both UI states "草稿" and
        "待提交" map to `created`). Anything that has been submitted /
        paid / closed falls outside this endpoint — for those, the user
        should use cancel (`status → closed`) or contact support.

        Behaviour (W67 decision — soft-delete materials):
          1. Verify ownership + status gate (404 on foreign/no-exist, 4010
             on status mismatch — same convention as cancel).
          2. Soft-delete every Material row referenced by the order
             (`deleted_at = now`). The file on disk is preserved for
             audit / recovery; the user will not see these materials in
             the library any more.
          3. Append one `OrderStatusHistory` row (source='user',
             note='draft deleted') so the audit trail of the order
             itself is captured before the row goes away.
          4. Physically delete the Order row + its `order_status_history`
             (cascade) + `order_messages` (cascade). Audit log row is
             written BEFORE the delete so it survives.
          5. record_audit(action='order.delete_draft', ...) — admin can
             find it from the audit log even though the order row is
             gone.

        Returns a small dict the API layer turns into DeleteDraftResponse.

        Note on the audit: we deliberately keep a *physical* audit row
        even though the order row is hard-deleted — admin / customer
        support need to be able to say "user X deleted draft order Y at
        time T". The audit table is append-only and never cascades.
        """
        order = await self._get_owned_order(user_id=user_id, order_no=order_no)
        if order.status not in CANCELLABLE_STATUSES:
            # Same gate as cancel — both are "user wants out of a draft
            # order" actions. We use 4010 ORDER_NOT_EDITABLE so the
            # front-end's existing handler (which already routes on
            # 4010 for cancel) catches it transparently.
            raise BizException(
                ErrorCode.ORDER_NOT_EDITABLE,
                message=(
                    f"Order in status '{order.status}' cannot be deleted as "
                    "a draft; only 'created' orders can be hard-deleted."
                ),
                data={"order_no": order_no, "current_status": order.status},
            )

        # 1) Snapshot the material ids we need to soft-delete. Decoding
        #    first avoids holding the order object open across the
        #    subsequent cascade delete.
        material_ids = self._decode_material_ids(order.material_ids)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        order_id = order.id

        # 2) Append the terminal status-history row before the cascade
        #    wipes them. The (from_status='created', to_status='created',
        #    source='user', note='draft deleted') combination is the
        #    audit signal that the order was hard-deleted, even though
        #    no status transition actually happened (status stays
        #    'created' until the row goes away).
        self.db.add(
            OrderStatusHistory(
                order_id=order_id,
                from_status=order.status,
                to_status=order.status,
                source="user",
                note="draft deleted (cascade)",
            )
        )
        await self.db.flush()  # ensure history row materialises before we wipe

        # 3) Soft-delete associated materials. We use a single UPDATE
        #    rather than N row-by-row updates — same effect, one
        #    round-trip, and idempotent on already-deleted rows.
        if material_ids:
            from sqlalchemy import update

            await self.db.execute(
                update(Material)
                .where(
                    Material.id.in_(material_ids),
                    Material.user_id == user_id,
                    Material.deleted_at.is_(None),  # only stamp once
                )
                .values(deleted_at=now)
            )

        # 4) Audit BEFORE delete — the audit table never cascades, so
        #    the row will survive the order's hard-delete. We record
        #    the material ids and the user so support can reconstruct
        #    the cascade.
        await record_audit(
            self.db,
            actor_type="user",
            actor_id=user_id,
            action="order.delete_draft",
            target_type="order",
            target_id=order_id,
            payload={
                "order_no": order_no,
                "soft_deleted_material_ids": material_ids,
                "deleted_at": now.isoformat(),
            },
        )

        # 5) Hard-delete the order row. SQLAlchemy cascades to
        #    order_status_history + order_messages (defined on the
        #    relationship). Audit log has no FK to orders so it's
        #    preserved.
        await self.db.delete(order)
        await self.db.commit()

        _log.info(
            "order draft deleted order_no={} user_id={} soft_materials={}",
            order_no, user_id, len(material_ids),
        )

        return {
            "order_no": order_no,
            "deleted": True,
            "soft_deleted_materials": len(material_ids),
            "deleted_at": now,
        }

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
    def _to_order_dict(
        order: Order,
        *,
        dest: Optional[VisaDestination] = None,
    ) -> Dict[str, Any]:
        country_code = ""
        country_name = ""
        if dest is not None:
            country_code = dest.country_code or ""
            country_name = OrderService._destination_display_name(dest)
        return {
            "id": order.id,
            "uuid": order.uuid,
            "order_no": order.order_no,
            "user_id": order.user_id,
            "destination_id": order.destination_id,
            "country_code": country_code,
            "country_name": country_name,
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
            "locked_until": order.locked_until,
            "paid_at": order.paid_at,
            "diagnosis_completed_at": order.diagnosis_completed_at,
            "completed_at": order.completed_at,
            "portal_submitted_at": order.portal_submitted_at,
            "portal_submitted_source": order.portal_submitted_source,
            "ds160_portal_submitted_at": order.ds160_portal_submitted_at or order.portal_submitted_at,
            "refund_status": order.refund_status or "none",
            "refund_reason": order.refund_reason,
            "refund_amount": order.refund_amount,
            "refund_requested_at": order.refund_requested_at,
            "refund_approved_at": order.refund_approved_at,
            "refunded_at": order.refunded_at,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }

    # ------------------------------------------------------------------ #
    # Order number generation                                             #
    # ------------------------------------------------------------------ #
    async def _generate_order_no(self) -> str:
        """Generate `V2-YYYYMMDD-XXXXXXXX` that's globally unique.

        Suffix is 8 hex chars from uuid4 (32-bit uniqueness space → ~1 in
        4 billion collision odds per attempt). Probe DB for existence and
        retry on collision; 5 attempts × 32-bit space = effectively zero
        conflict probability under realistic load.

        The previous per-day count-then-insert strategy had a read-write
        race: 15 concurrent creates all read the same count=N, all picked
        candidate=N+1, then 14 of them crashed with `concurrent order_no
        conflict` at flush time. Switched to uuid suffix to eliminate the
        race entirely.
        """
        today_prefix = "V2-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-"
        for attempt in range(5):
            candidate = f"{today_prefix}{uuid.uuid4().hex[:8].upper()}"
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
