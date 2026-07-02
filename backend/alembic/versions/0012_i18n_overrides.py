"""Add i18n_overrides table (V0 §4.4.4 — multi-language copy override).

Revision ID: 0012_i18n_overrides
Revises: 0010_admin_roles_users
Create Date: 2026-06-30 19:00:00.000000

- i18n_overrides : 运营文案覆盖表（优先级高于前端内置 json）
  - id, locale, key, value, original_value (前端内置 json 的原值, diff 用)
  - updated_by_admin_id, updated_at, created_at
  - unique(locale, key) 保证一个 locale+key 只有一条覆盖
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0012_i18n_overrides"
down_revision = "0011_countries_extend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "i18n_overrides",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("key", sa.String(length=256), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("original_value", sa.Text(), nullable=True),
        sa.Column("updated_by_admin_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("locale", "key", name="uq_i18n_overrides_locale_key"),
    )
    op.create_index("ix_i18n_overrides_locale", "i18n_overrides", ["locale"])
    op.create_index("ix_i18n_overrides_key", "i18n_overrides", ["key"])


def downgrade() -> None:
    op.drop_index("ix_i18n_overrides_key", table_name="i18n_overrides")
    op.drop_index("ix_i18n_overrides_locale", table_name="i18n_overrides")
    op.drop_table("i18n_overrides")