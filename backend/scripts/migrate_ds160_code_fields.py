"""One-shot migration for the W48 v0.2 DS-160 code columns.

Adds 6 columns to `orders`:
    ds160_code                VARCHAR(12)  NULL  indexed
    ds160_fingerprint         VARCHAR(64)  NULL
    ds160_code_issued_at      TIMESTAMP    NULL
    ds160_code_consumed_count INTEGER      NOT NULL DEFAULT 0
    ds160_last_redeemed_at    TIMESTAMP    NULL
    ds160_code_revoked        BOOLEAN      NOT NULL DEFAULT 0

Designed to be idempotent: each ALTER checks sqlite_master / pg_catalog
before running, so re-running this script is a no-op.

Run:
    cd backend
    PYTHONPATH=. .venv/bin/python scripts/migrate_ds160_code_fields.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.core.logging import get_logger  # noqa: E402

_log = get_logger()

# (column_name, SQL type, default_clause_or_None)
_COLUMNS: list[tuple[str, str, str | None]] = [
    ("ds160_code", "VARCHAR(12)", None),
    ("ds160_fingerprint", "VARCHAR(64)", None),
    ("ds160_code_issued_at", "TIMESTAMP", None),
    ("ds160_code_consumed_count", "INTEGER", "0"),
    ("ds160_last_redeemed_at", "TIMESTAMP", None),
    ("ds160_code_revoked", "BOOLEAN", "0"),
    ("ds160_revoked_codes", "TEXT", None),
]

_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS ix_orders_ds160_code ON orders (ds160_code)",
]


async def _column_exists(conn, table: str, column: str) -> bool:
    """Cross-dialect column existence check (SQLite + Postgres).

    For SQLite we inspect pragma_table_info; for Postgres we use information_schema.
    Both branches return True when the column is already present.
    """
    if conn.dialect.name == "sqlite":
        rows = await conn.execute(text(f"PRAGMA table_info({table})"))
        cols = {r[1] for r in rows.fetchall()}
        return column in cols
    rows = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return rows.first() is not None


async def main() -> int:
    async with engine.begin() as conn:
        for col, sql_type, default in _COLUMNS:
            if await _column_exists(conn, "orders", col):
                _log.info("skip %s (already exists)", col)
                continue
            default_clause = f" DEFAULT {default}" if default is not None else ""
            # SQLite is happy with both INTEGER and BOOLEAN; Postgres wants BOOLEAN
            # for the boolean column. We use the literal BOOLEAN keyword; SQLAlchemy
            # / aiosqlite will coerce as needed.
            stmt = f"ALTER TABLE orders ADD COLUMN {col} {sql_type}{default_clause}"
            _log.info("add column orders.%s (%s)", col, sql_type)
            await conn.execute(text(stmt))

        for ddl in _INDEXES:
            _log.info("ensure index: %s", ddl)
            await conn.execute(text(ddl))

        _log.info("migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))