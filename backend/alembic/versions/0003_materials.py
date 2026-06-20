"""materials 表 — V2 §4.3 (File Service)

Revision ID: 0003_materials
Revises: 0002_destinations
Create Date: 2026-06-11 20:20:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0003_materials"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=36), nullable=False, unique=True),
        # ownership
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        # classification
        sa.Column("material_type", sa.String(length=32), nullable=False),
        # file metadata
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        # storage
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("thumbnail_key", sa.String(length=512), nullable=True),
        sa.Column(
            "encryption_key_id",
            sa.String(length=64),
            nullable=False,
            server_default="dev-kms-stub",
        ),
        # async OCR / classification results
        sa.Column(
            "ocr_status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("ocr_result", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(length=32), nullable=True),
        sa.Column("classification_corrected", sa.String(length=32), nullable=True),
        # business expiry (e.g. passport validity)
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        # lifecycle
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    # ---- indexes (mirror app/models/material.py) ----
    op.create_index("ix_materials_uuid", "materials", ["uuid"], unique=True)
    op.create_index("ix_materials_user_id", "materials", ["user_id"], unique=False)
    op.create_index("ix_materials_order_id", "materials", ["order_id"], unique=False)
    op.create_index("ix_materials_type", "materials", ["material_type"], unique=False)
    op.create_index(
        "idx_materials_user_created", "materials", ["user_id", "created_at"]
    )
    op.create_index("idx_materials_ocr_pending", "materials", ["ocr_status"])

    # ---- de-dup: same sha256 + same user is unique for non-deleted rows ----
    # SQLite allows multiple NULL values in a unique column, so soft-deleted
    # rows (where deleted_at IS NOT NULL) won't conflict and the user can
    # re-upload after delete. Active rows share one sha256/user slot.
    op.create_index(
        "uq_materials_sha_user_alive",
        "materials",
        ["sha256", "user_id", "deleted_at"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_materials_sha_user_alive", table_name="materials")
    op.drop_index("idx_materials_ocr_pending", table_name="materials")
    op.drop_index("idx_materials_user_created", table_name="materials")
    op.drop_index("ix_materials_type", table_name="materials")
    op.drop_index("ix_materials_order_id", table_name="materials")
    op.drop_index("ix_materials_user_id", table_name="materials")
    op.drop_index("ix_materials_uuid", table_name="materials")
    op.drop_table("materials")
