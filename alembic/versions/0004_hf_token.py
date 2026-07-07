"""Add hf_token_encrypted to user_settings

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("hf_token_encrypted", sa.LargeBinary, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "hf_token_encrypted")
