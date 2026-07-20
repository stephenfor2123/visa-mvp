"""Add missing users identity/OAuth columns (email, username, google_sub, …).

Revision ID: 0025_user_oauth_identity
Revises: 0024_platform_pricing

Why:
  Google / WeChat login and email+password auth require columns that exist on
  the SQLAlchemy User model but were never added by an alembic revision.
  Production DBs that only ran `alembic upgrade` (no create_all) therefore
  crash on Google login with an unhandled OperationalError → HTTP 500.
  Cloudflare often strips CORS headers on 5xx, so the browser shows
  axios "Network Error" instead of the real server message.

Idempotent: skips any column / index that already exists (safe for local DBs
that got these columns via create_all).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0025_user_oauth_identity"
down_revision = "0024_platform_pricing"
branch_labels = None
depends_on = None


def _cols(insp) -> set[str]:
    return {c["name"] for c in insp.get_columns("users")}


def _indexes(insp) -> set[str]:
    return {idx["name"] for idx in insp.get_indexes("users") if idx.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = _cols(insp)
    idxs = _indexes(insp)

    with op.batch_alter_table("users") as batch_op:
        if "email" not in cols:
            batch_op.add_column(sa.Column("email", sa.String(length=120), nullable=True))
        if "username" not in cols:
            batch_op.add_column(sa.Column("username", sa.String(length=32), nullable=True))
        if "google_sub" not in cols:
            batch_op.add_column(sa.Column("google_sub", sa.String(length=128), nullable=True))
        if "wechat_openid" not in cols:
            batch_op.add_column(sa.Column("wechat_openid", sa.String(length=64), nullable=True))
        if "mfa_enabled" not in cols:
            batch_op.add_column(
                sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
            )
        if "mfa_type" not in cols:
            batch_op.add_column(sa.Column("mfa_type", sa.String(length=16), nullable=True))
        if "mfa_secret" not in cols:
            batch_op.add_column(sa.Column("mfa_secret", sa.String(length=255), nullable=True))

    # Indexes outside batch — skip any that already exist.
    insp = sa.inspect(bind)
    cols = _cols(insp)
    idxs = _indexes(insp)

    def _ensure_index(name: str, columns: list[str], unique: bool = False) -> None:
        if name in idxs:
            return
        if not all(c in cols for c in columns):
            return
        op.create_index(name, "users", columns, unique=unique)

    _ensure_index("ix_users_email", ["email"], unique=True)
    _ensure_index("ix_users_username", ["username"], unique=True)
    _ensure_index("ix_users_google_sub", ["google_sub"], unique=True)
    _ensure_index("ix_users_wechat_openid", ["wechat_openid"], unique=True)
    _ensure_index("ix_users_mfa_enabled", ["mfa_enabled"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = _cols(insp)
    idxs = _indexes(insp)

    for name in (
        "ix_users_mfa_enabled",
        "ix_users_wechat_openid",
        "ix_users_google_sub",
        "ix_users_username",
        "ix_users_email",
    ):
        if name in idxs:
            op.drop_index(name, table_name="users")

    with op.batch_alter_table("users") as batch_op:
        for col in (
            "mfa_secret",
            "mfa_type",
            "mfa_enabled",
            "wechat_openid",
            "google_sub",
            "username",
            "email",
        ):
            if col in cols:
                batch_op.drop_column(col)
