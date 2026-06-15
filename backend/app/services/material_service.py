"""MaterialService — upload / fetch / soft-delete / dedup / validate.

V2 §4.3. The same file (sha256) uploaded twice by the same user returns
the existing row instead of creating a new one (the `deduplicated` flag
on the response tells the client which case it is).
"""
import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.models.material import (
    MATERIAL_TYPES,
    OCR_STATUSES,
    Material,
)
from app.services import storage
from app.services.audit import record_audit
from app.services.validation import (
    DEFAULT_RULES,
    MaterialRef,
    ValidationEngine,
    overall as issues_overall,
)


_log = get_logger()


class MaterialService:
    """Owns the material lifecycle (without async OCR — that's W3+)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    # ------------------------------------------------------------------ #
    # Upload                                                              #
    # ------------------------------------------------------------------ #
    async def upload(
        self,
        *,
        user_id: int,
        original_filename: str,
        mime_type: str,
        data: bytes,
        material_type: str,
        order_no: Optional[str] = None,
    ) -> tuple[Material, bool]:
        """Persist a new material (or de-dup against an existing row).

        Returns (material, deduplicated). Caller should mark `deduplicated`
        in the HTTP response so the frontend can decide UX (toast vs. silent).
        """
        if material_type not in MATERIAL_TYPES:
            raise BizException(
                ErrorCode.INVALID_PARAMS,
                message=f"material_type must be one of {sorted(MATERIAL_TYPES)}",
            )
        if not data:
            raise BizException(
                ErrorCode.INVALID_PARAMS, message="file is empty"
            )
        max_bytes = self.settings.material_max_file_size_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise BizException(
                ErrorCode.INVALID_PARAMS,
                message=(
                    f"file too large: {len(data)} > "
                    f"{self.settings.material_max_file_size_mb}MB"
                ),
                data={
                    "size": len(data),
                    "max_bytes": max_bytes,
                },
            )

        sha256 = storage.compute_sha256(data)
        mime_type = (mime_type or "").lower() or _guess_mime(original_filename)

        # De-dup: same sha256 + same user, not soft-deleted
        existing = await self._find_dedup(user_id, sha256)
        if existing is not None:
            _log.info(
                "material dedup hit user_id={} sha256={} -> material_id={}",
                user_id,
                sha256[:8],
                existing.id,
            )
            return existing, True

        ext = os.path.splitext(original_filename or "")[1].lstrip(".") or "bin"
        stored = storage.store_bytes(user_id=user_id, ext=ext, data=data)

        row = Material(
            user_id=user_id,
            order_id=None,  # order_id 关联后续 W3+
            material_type=material_type,
            original_filename=(original_filename or "file")[:255],
            mime_type=mime_type[:64],
            file_size=stored.size,
            sha256=sha256,
            storage_key=stored.storage_key,
            thumbnail_key=None,  # 缩略图生成留给 W3 (Pillow)
            encryption_key_id="dev-kms-stub",
            ocr_status="pending",
        )
        self.db.add(row)
        await self.db.flush()

        await record_audit(
            self.db,
            actor_type="user",
            actor_id=user_id,
            action="material.upload",
            target_type="material",
            target_id=row.id,
            payload={
                "material_type": material_type,
                "size": stored.size,
                "sha256_prefix": sha256[:8],
                "order_no": order_no,
                "mime_type": mime_type,
            },
        )
        await self.db.commit()
        await self.db.refresh(row)
        _log.info("material uploaded id={} user={} size={}", row.id, user_id, stored.size)
        return row, False

    # ------------------------------------------------------------------ #
    # Get / soft-delete                                                   #
    # ------------------------------------------------------------------ #
    async def get(self, *, user_id: int, material_id: int) -> Material:
        row = await self._get_owned(user_id, material_id)
        return row

    async def get_detail(self, *, user_id: int, material_id: int) -> dict[str, Any]:
        """Return row as a dict with ocr_result parsed to a JSON object."""
        row = await self._get_owned(user_id, material_id)
        out = self._row_to_dict(row)
        if row.ocr_result:
            try:
                out["ocr_result"] = json.loads(row.ocr_result)
            except json.JSONDecodeError:
                out["ocr_result"] = None
        return out

    async def soft_delete(self, *, user_id: int, material_id: int) -> Material:
        row = await self._get_owned(user_id, material_id)
        if row.deleted_at is None:
            row.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await record_audit(
                self.db,
                actor_type="user",
                actor_id=user_id,
                action="material.soft_delete",
                target_type="material",
                target_id=row.id,
            )
            await self.db.commit()
            await self.db.refresh(row)
            _log.info("material soft-deleted id={} user={}", row.id, user_id)
        return row

    # ------------------------------------------------------------------ #
    # Signed URL helpers                                                  #
    # ------------------------------------------------------------------ #
    def build_download_url(self, row: Material, base_url: str = "") -> str:
        token, expires_at = storage.make_signed_token(
            row.storage_key, self.settings.material_url_ttl_seconds
        )
        return f"{base_url}/api/v2/materials/_local/{token}?key={row.storage_key}"

    def build_thumbnail_url(self, row: Material, base_url: str = "") -> Optional[str]:
        if not row.thumbnail_key:
            return None
        token, _ = storage.make_signed_token(
            row.thumbnail_key, self.settings.material_url_ttl_seconds
        )
        return f"{base_url}/api/v2/materials/_local/{token}?key={row.thumbnail_key}"

    # ------------------------------------------------------------------ #
    # Validate                                                            #
    # ------------------------------------------------------------------ #
    async def validate_materials(
        self,
        *,
        user_id: int,
        material_ids: list[int],
        fields: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not material_ids:
            raise BizException(
                ErrorCode.INVALID_PARAMS, message="material_ids must be non-empty"
            )
        # Load all rows in one shot, scoped to this user
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
        rows_by_id = {r.id: r for r in rows}
        missing = [mid for mid in material_ids if mid not in rows_by_id]
        if missing:
            raise BizException(
                ErrorCode.NOT_FOUND,
                message=f"materials not found: {missing}",
                data={"missing": missing},
            )

        # MaterialRef pulls just what the rules need
        refs: list[MaterialRef] = []
        for r in rows:
            ocr = None
            if r.ocr_result:
                try:
                    ocr = json.loads(r.ocr_result)
                except json.JSONDecodeError:
                    ocr = None
            refs.append(
                MaterialRef(
                    id=r.id,
                    material_type=r.material_type,
                    mime_type=r.mime_type,
                    file_size=r.file_size,
                    ocr_result=ocr,
                )
            )

        # We also feed a primary `file_meta` from the first material so
        # single-file rules (size, mime) work even when the engine is
        # called without `materials`. Materials list covers multi-file.
        file_meta: Optional[dict[str, Any]] = None
        if refs:
            file_meta = {
                "mime_type": refs[0].mime_type,
                "size_bytes": refs[0].file_size,
            }

        engine = ValidationEngine.from_default()
        issues = engine.run(fields=fields or {}, materials=refs, file_meta=file_meta)
        verdict = issues_overall(issues)
        return {
            "overall": verdict,
            "issues": issues,
            "rule_count": engine.rule_count,
            "materials_checked": len(refs),
            "fields_checked": dict(fields or {}),
        }

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #
    async def _find_dedup(
        self, user_id: int, sha256: str
    ) -> Optional[Material]:
        """Active (non soft-deleted) row with same (sha256, user_id)."""
        return await self.db.scalar(
            select(Material).where(
                and_(
                    Material.user_id == user_id,
                    Material.sha256 == sha256,
                    Material.deleted_at.is_(None),
                )
            )
        )

    async def _get_owned(
        self, user_id: int, material_id: int
    ) -> Material:
        row = await self.db.get(Material, material_id)
        if row is None or row.deleted_at is not None:
            raise BizException(
                ErrorCode.NOT_FOUND, message=f"material {material_id} not found"
            )
        if row.user_id != user_id:
            # Don't leak the existence of someone else's row.
            raise BizException(
                ErrorCode.NOT_FOUND, message=f"material {material_id} not found"
            )
        return row

    @staticmethod
    def _row_to_dict(row: Material) -> dict[str, Any]:
        return {
            "id": row.id,
            "uuid": row.uuid,
            "user_id": row.user_id,
            "order_id": row.order_id,
            "material_type": row.material_type,
            "original_filename": row.original_filename,
            "mime_type": row.mime_type,
            "file_size": row.file_size,
            "sha256": row.sha256,
            "storage_key": row.storage_key,
            "thumbnail_key": row.thumbnail_key,
            "encryption_key_id": row.encryption_key_id,
            "ocr_status": row.ocr_status,
            "classification": row.classification,
            "classification_corrected": row.classification_corrected,
            "expires_at": row.expires_at,
            "archived": row.archived,
            "created_at": row.created_at,
        }


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _guess_mime(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename or "")
    return mime or "application/octet-stream"
