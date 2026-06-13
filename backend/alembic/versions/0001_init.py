"""initial schema (4 tables) — V2 §4.1.4

Revision ID: 0001_init
Revises:
Create Date: 2026-06-11 17:05:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- users ----
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=36), nullable=False, unique=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("phone_country", sa.String(length=8), nullable=False, server_default="+86"),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("nickname", sa.String(length=64), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("language_pref", sa.String(length=8), nullable=False, server_default="zh-CN"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("last_login_ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_phone", "users", ["phone"], unique=False)
    op.create_index("ix_users_uuid", "users", ["uuid"], unique=True)
    op.create_index("ix_users_nickname", "users", ["nickname"], unique=False)
    op.create_index("ix_users_status", "users", ["status"], unique=False)
    # Phone (with country) must be unique together
    op.create_index(
        "uq_users_phone_country",
        "users",
        ["phone_country", "phone"],
        unique=True,
    )

    # ---- user_sessions ----
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=36), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_sessions_user_id", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
    op.create_index(
        "ix_user_sessions_refresh_token_hash",
        "user_sessions",
        ["refresh_token_hash"],
        unique=False,
    )
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"], unique=False)
    op.create_index("ix_user_sessions_uuid", "user_sessions", ["uuid"], unique=True)

    # ---- sms_codes ----
    op.create_table(
        "sms_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("phone_country", sa.String(length=8), nullable=False, server_default="+86"),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("send_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sms_codes_phone", "sms_codes", ["phone"], unique=False)
    op.create_index("ix_sms_codes_purpose", "sms_codes", ["purpose"], unique=False)
    op.create_index("ix_sms_codes_expires_at", "sms_codes", ["expires_at"], unique=False)
    op.create_index(
        "ix_sms_codes_phone_purpose", "sms_codes", ["phone", "phone_country", "purpose"]
    )

    # ---- audit_log ----
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=36), nullable=False, unique=True),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"], unique=False)
    op.create_index("ix_audit_log_action", "audit_log", ["action"], unique=False)
    op.create_index("ix_audit_log_target_type", "audit_log", ["target_type"], unique=False)
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"], unique=False)
    op.create_index(
        "ix_audit_log_actor_action", "audit_log", ["actor_type", "actor_id", "action"]
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_actor_action", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_target_type", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_id", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_sms_codes_phone_purpose", table_name="sms_codes")
    op.drop_index("ix_sms_codes_expires_at", table_name="sms_codes")
    op.drop_index("ix_sms_codes_purpose", table_name="sms_codes")
    op.drop_index("ix_sms_codes_phone", table_name="sms_codes")
    op.drop_table("sms_codes")

    op.drop_index("ix_user_sessions_uuid", table_name="user_sessions")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_refresh_token_hash", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")

    op.drop_index("uq_users_phone_country", table_name="users")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_nickname", table_name="users")
    op.drop_index("ix_users_uuid", table_name="users")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_table("users")
