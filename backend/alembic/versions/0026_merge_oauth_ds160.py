"""Merge OAuth identity head with ds160_code_hash branch.

Revision ID: 0026_merge_oauth_ds160
Revises: 0025_user_oauth_identity, 0021_ds160_code_hash
"""
from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0026_merge_oauth_ds160"
down_revision = ("0025_user_oauth_identity", "0021_ds160_code_hash")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
