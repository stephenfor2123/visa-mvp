"""orders + order_status_history + order_messages 表 — V2 §4.2

Revision ID: 0004_orders
Revises: 0003_materials
Create Date: 2026-06-11 20:30:00.000000

Creates 3 tables for the Order Service:
  - orders                  main order row + V2-YYYYMMDD-NNNNNN business number
  - order_status_history    append-only state-transition log (V2 §4.2.4)
  - order_messages          per-order notifications

SQLite-friendly types:
  - JSONB        -> Text  (JSON 字符串)
  - BIGINT[]     -> Text  (JSON 字符串数组)
  - NUMERIC(10,2)-> Numeric
  - TIMESTAMPTZ  -> DateTime
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0004_orders"
down_revision = "0003_materials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- orders ----
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=36), nullable=False, unique=True),
        sa.Column("order_no", sa.String(length=32), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("visa_type", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="created",
        ),
        sa.Column(
            "total_amount",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "currency",
            sa.String(length=8),
            nullable=False,
            server_default="USD",
        ),
        sa.Column("rpa_task_id", sa.String(length=64), nullable=True),
        sa.Column("destination_url", sa.Text(), nullable=True),
        sa.Column("applicant_data", sa.Text(), nullable=True),
        sa.Column("material_ids", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("extra", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["destination_id"],
            ["visa_destinations.id"],
            name="fk_orders_destination_id",
        ),
    )
    # Indexes
    op.create_index("ix_orders_uuid", "orders", ["uuid"], unique=True)
    op.create_index("ix_orders_order_no", "orders", ["order_no"], unique=True)
    op.create_index("ix_orders_user_id", "orders", ["user_id"], unique=False)
    op.create_index(
        "ix_orders_destination_id", "orders", ["destination_id"], unique=False
    )
    op.create_index("ix_orders_status", "orders", ["status"], unique=False)
    op.create_index("ix_orders_rpa_task_id", "orders", ["rpa_task_id"], unique=False)
    op.create_index(
        "idx_orders_user_created", "orders", ["user_id", "created_at"]
    )

    # ---- order_status_history ----
    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_status_history_order_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_order_status_history_order_id",
        "order_status_history",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        "idx_status_history_order",
        "order_status_history",
        ["order_id", "created_at"],
    )

    # ---- order_messages ----
    op.create_table(
        "order_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_order_messages_order_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_order_messages_order_id",
        "order_messages",
        ["order_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_order_messages_order_id", table_name="order_messages")
    op.drop_table("order_messages")

    op.drop_index("idx_status_history_order", table_name="order_status_history")
    op.drop_index("ix_order_status_history_order_id", table_name="order_status_history")
    op.drop_table("order_status_history")

    op.drop_index("idx_orders_user_created", table_name="orders")
    op.drop_index("ix_orders_rpa_task_id", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_destination_id", table_name="orders")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_index("ix_orders_order_no", table_name="orders")
    op.drop_index("ix_orders_uuid", table_name="orders")
    op.drop_table("orders")
