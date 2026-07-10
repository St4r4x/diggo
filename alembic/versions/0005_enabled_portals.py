"""Replace portal_queries with enabled_portals on user_settings

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("user_settings", "portal_queries")
    op.add_column(
        "user_settings",
        sa.Column(
            "enabled_portals", sa.ARRAY(sa.Text), nullable=False, server_default="{}"
        ),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "enabled_portals")
    op.add_column(
        "user_settings",
        sa.Column(
            "portal_queries", sa.ARRAY(sa.Text), nullable=False, server_default="{}"
        ),
    )
