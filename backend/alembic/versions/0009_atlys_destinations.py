"""Add visa_fee / valid_days / process_days to visa_destinations (Atlys-style cards).

Revision ID: 0009_atlys_destinations
Revises: 0008_webhook_events
Create Date: 2026-06-26 10:35:00.000000

Three new columns on visa_destinations so the Home page country cards can show:
  - visa_fee_usd  : integer cents (avoid float money) — maps to "FEES: $XX" chip
  - valid_days    : visa validity in days, e.g. 730 -> "VALID: 2 YEARS"
  - process_days  : typical processing time in days, used to compute a precise
                    ETA ISO timestamp on the server ("Guaranteed Visa on …").

Also seeds 4 hero countries (US/AU/GB/SCHENGEN) + 26 Schengen members with
illustrative figures so the UI has real numbers to render.  Numbers are for
display only — actual billing happens via Stripe, not from this column.

Reversible via DROP COLUMN (SQLite ≥ 3.35 supports it).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0009_atlys_destinations"
down_revision = "0008_webhook_events"
branch_labels = None
depends_on = None


# --- seed data -------------------------------------------------------------
# (country_code, fee_usd_cents, valid_days, process_days)
#  - SCHENGEN row is special — see seed_schengen_26.py for the 26 sub-entries.
#  - All figures are display-only.  Stripe pricing is set in payment config.
DEFAULT_ROWS = [
    # hero 4
    ("US",       18500, 365,  5),  # $185, 1 year, 5 days
    ("AU",       14500, 365,  4),  # $145, 1 year, 4 days
    ("GB",       12500, 180,  3),  # $125, 6 months, 3 days
    ("SCHENGEN",  9000, 180,  7),  # $90, 6 months, 7 days (placeholder; not seeded into destinations table)
    # 26 schengen members
    ("AT",  9000, 180,  7),
    ("BE",  9000, 180,  7),
    ("HR",  9000, 180,  7),
    ("CZ",  9000, 180,  7),
    ("DK",  9000, 180,  7),
    ("EE",  9000, 180,  7),
    ("FI",  9000, 180,  7),
    ("FR",  9000, 180,  7),
    ("DE",  9000, 180,  7),
    ("GR",  9000, 180,  7),
    ("HU",  9000, 180,  7),
    ("IS",  9000, 180,  7),
    ("IT",  9000, 180,  7),
    ("LV",  9000, 180,  7),
    ("LI",  9000, 180,  7),
    ("LT",  9000, 180,  7),
    ("LU",  9000, 180,  7),
    ("MT",  9000, 180,  7),
    ("NL",  9000, 180,  7),
    ("NO",  9000, 180,  7),
    ("PL",  9000, 180,  7),
    ("PT",  9000, 180,  7),
    ("SK",  9000, 180,  7),
    ("SI",  9000, 180,  7),
    ("ES",  9000, 180,  7),
    ("SE",  9000, 180,  7),
]


def upgrade() -> None:
    # 1. add columns (nullable so existing rows don't fail)
    with op.batch_alter_table("visa_destinations") as batch:
        batch.add_column(
            sa.Column(
                "visa_fee_usd",
                sa.Integer(),
                nullable=True,
                comment="Price in USD cents — display only, billing via Stripe",
            )
        )
        batch.add_column(
            sa.Column(
                "valid_days",
                sa.Integer(),
                nullable=True,
                comment="Visa validity in days (e.g. 730 = 2 years)",
            )
        )
        batch.add_column(
            sa.Column(
                "process_days",
                sa.Integer(),
                nullable=True,
                comment="Typical processing days — used to compute ETA timestamp",
            )
        )

    # 2. seed rows that exist; SCHENGEN row is virtual, skip if absent
    bind = op.get_bind()
    for code, fee_cents, valid, proc in DEFAULT_ROWS:
        bind.execute(
            sa.text(
                "UPDATE visa_destinations "
                "SET visa_fee_usd = :fee, valid_days = :valid, process_days = :proc "
                "WHERE country_code = :code"
            ),
            {"fee": fee_cents, "valid": valid, "proc": proc, "code": code},
        )


def downgrade() -> None:
    with op.batch_alter_table("visa_destinations") as batch:
        batch.drop_column("process_days")
        batch.drop_column("valid_days")
        batch.drop_column("visa_fee_usd")