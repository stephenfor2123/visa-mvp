"""Material ORM model — V2 §4.3 (File Service).

Stores metadata for user-uploaded visa materials. The actual binary lives
under `data/materials/{user_id}/{storage_key}` (local FS stand-in for
MinIO in W2). Sha256 + user_id is uniquely indexed so the same file
uploaded twice by the same user is de-duplicated (returns the existing
row).
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


# Material lifecycle: ocr_status: pending / processing / done / failed
OCR_STATUSES = ("pending", "processing", "done", "failed")
# Material types per V2 §4.3.2 — passport / id_card / household / enrollment / photo / form / other
# W36: added bank / employment / hotel / flight / insurance — the material
# wizard's financial / work / travel / insurance categories. Frontend
# (api/materials.js getMaterialTypeOptions) already listed bank/flight/hotel
# as options before the backend accepted them; this closes that gap.
MATERIAL_TYPES = (
    "passport",
    "id_card",
    "household",
    "enrollment",
    "photo",
    "form",
    "bank",
    "employment",
    "hotel",
    "flight",
    "insurance",
    "other",
)


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_new_uuid)

    # Ownership
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # order_id is nullable: per V2 §4.3.2 a material can be uploaded
    # before it's associated with a specific order. FK is intentionally
    # omitted here because the orders table is not yet in scope (W3+).
    order_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Classification
    material_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # File metadata
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    # Storage
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    encryption_key_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="dev-kms-stub"
    )

    # Async OCR / classification results (populated by Celery in W3+)
    ocr_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="pending"
    )
    ocr_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 字符串
    classification: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    classification_corrected: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )

    # Business expiry (e.g. passport validity)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Lifecycle
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Same file uploaded twice by the same user is treated as a no-op
    # (returns the original row) — covered by UQ sha256+user_id.
    # Soft-deleted rows are EXCLUDED so a user can re-upload after delete.
    __table_args__ = (
        UniqueConstraint(
            "sha256",
            "user_id",
            "deleted_at",
            name="uq_materials_sha_user_alive",
        ),
        Index("idx_materials_user_created", "user_id", "created_at"),
        Index("idx_materials_ocr_pending", "ocr_status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<Material id={self.id} type={self.material_type} user={self.user_id}>"
