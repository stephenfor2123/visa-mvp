"""ds160 browser extension fields on orders table (W48 v0.2)

Revision ID: 0019_ds160
Revises: 0018_rag_review_workflow
Create Date: 2026-07-09 13:30:00.000000

Adds 6 columns to orders table for DS-160 browser extension support:
  - ds160_code                  12-char base30 code (index)
  - ds160_fingerprint           SHA-256 hex of normalized applicant_data
  - ds160_code_issued_at        when user requested the code
  - ds160_code_consumed_count   successful redeem attempts (default 0)
  - ds160_last_redeemed_at      last successful redeem timestamp
  - ds160_code_revoked          manual rotate flag (default false)

These columns are required by app/models/order.py (lines 198-220) and
app/core/ds160.py — SELECTs against orders fail with
"(sqlite3.OperationalError) no such column: orders.ds160_code"
until this migration runs.

Safe to re-run: each column uses IF NOT EXISTS-equivalent (alembic
op.add_column is a no-op if column exists when using batch mode; on
SQLite we use a guarded pattern via PRAGMA check).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0019_ds160"
down_revision = "0018_rag_review_workflow"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    """SQLite-safe check: PRAGMA table_info to detect existing column."""
    conn = op.get_bind()
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def upgrade() -> None:
    cols_to_add = [
        ("ds160_code", sa.String(length=12), True, None),
        ("ds160_fingerprint", sa.String(length=64), True, None),
        ("ds160_code_issued_at", sa.DateTime(), True, None),
        ("ds160_code_consumed_count", sa.Integer(), False, "0"),
        ("ds160_last_redeemed_at", sa.DateTime(), True, None),
        ("ds160_code_revoked", sa.Boolean(), False, "0"),
        # W48.1: 历史撤销码 JSON list, 用于 rate-limit 旧码
        ("ds160_revoked_codes", sa.Text(), True, None),
    ]
    for col_name, col_type, nullable, server_default in cols_to_add:
        if not _has_column("orders", col_name):
            op.add_column(
                "orders",
                sa.Column(
                    col_name,
                    col_type,
                    nullable=nullable,
                    server_default=server_default,
                ),
            )
    # Index on ds160_code for /api/v2/ds160/code lookup
    try:
        op.create_index("ix_orders_ds160_code", "orders", ["ds160_code"])
    except Exception:
        pass  # index may already exist; sqlite gives "already exists"


def downgrade() -> None:
    for col_name in [
        "ds160_code",
        "ds160_fingerprint",
        "ds160_code_issued_at",
        "ds160_code_consumed_count",
        "ds160_last_redeemed_at",
        "ds160_code_revoked",
    ]:
        if _has_column("orders", col_name):
            op.drop_column("orders", col_name)
