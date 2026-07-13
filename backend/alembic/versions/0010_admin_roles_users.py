"""Add admin_roles + admin_users tables (W34 权限系统).

Revision ID: 0010_admin_roles_users
Revises: 0009_atlys_destinations
Create Date: 2026-06-30 18:00:00.000000

- admin_roles    : 角色表（超级管理员 / 员工）
- admin_users    : 管理员用户表（独立于 C-user）

初始数据：
  超级管理员 (super_admin): 所有权限 ["dashboard","orders","payments","users","countries","settings"]
  员工 (staff): 基础权限 ["dashboard","orders","payments"]
  初始账号: admin / Admin@2024 (bcrypt 哈希)

历史说明: 2026-07-07 之后, demo admin 密码已统一改为 8 位 `HtexAd@26`
(见 backend/scripts/seed_demo_data.py + backend/.env ADMIN_PASSWORD_SECRET)。
本 migration 的 docstring / seed 哈希保留 W34 当时的快照, 不做变更 — 改它会
破坏 alembic 审计链。如果需要从旧哈希迁到新哈希, 请新建一个后续 migration
(W47c+) 而不是改这一条。
"""
from __future__ import annotations

import bcrypt
import json
import sqlalchemy as sa
from alembic import op


revision = "0010_admin_roles_users"
down_revision = "0009_atlys_destinations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # admin_roles
    op.create_table(
        "admin_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=32), unique=True, nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_roles_code", "admin_roles", ["code"], unique=True)

    # admin_users
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("admin_roles.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=True)

    # Seed roles (permissions as JSON string via text())
    super_admin_perms = json.dumps(["dashboard", "orders", "payments", "users", "countries", "settings"])
    staff_perms = json.dumps(["dashboard", "orders", "payments"])
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO admin_roles (name, code, permissions, description) "
            "VALUES (:name, :code, :perms, :desc)"
        ),
        {"name": "超级管理员", "code": "super_admin", "perms": super_admin_perms, "desc": "拥有所有后台权限"},
    )
    bind.execute(
        sa.text(
            "INSERT INTO admin_roles (name, code, permissions, description) "
            "VALUES (:name, :code, :perms, :desc)"
        ),
        {"name": "员工", "code": "staff", "perms": staff_perms, "desc": "基础操作权限，不可管理用户和国家配置"},
    )

    # Seed default admin user (password: Admin@2024)
    pw_hash = bcrypt.hashpw("Admin@2024".encode(), bcrypt.gensalt()).decode()
    bind.execute(
        sa.text("INSERT INTO admin_users (username, password_hash, role_id) VALUES (:username, :pw, :role_id)"),
        {"username": "admin", "pw": pw_hash, "role_id": 1},
    )


def downgrade() -> None:
    op.drop_index("ix_admin_users_username", table_name="admin_users")
    op.drop_table("admin_users")
    op.drop_index("ix_admin_roles_code", table_name="admin_roles")
    op.drop_table("admin_roles")