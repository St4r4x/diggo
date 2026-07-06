"""Add prep_sheet_path to applications

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("prep_sheet_path", sa.Text, nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("applications", "prep_sheet_path")
