"""Initial schema with user_id

Revision ID: 0001
Revises:
Create Date: 2026-07-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("company", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("offer_url", sa.Text, nullable=False, server_default=""),
        sa.Column("detection_date", sa.Text, nullable=False),
        sa.Column("score_grade", sa.Text, nullable=False, server_default=""),
        sa.Column("score_value", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("status", sa.Text, nullable=False, server_default="À envoyer"),
        sa.Column("send_date", sa.Text, nullable=True),
        sa.Column("contacts", sa.Text, nullable=False, server_default=""),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("cv_path", sa.Text, nullable=False, server_default=""),
        sa.Column("cover_letter_path", sa.Text, nullable=False, server_default=""),
        sa.Column("follow_up_date", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("portal", sa.Text, nullable=False, server_default=""),
    )
    op.create_index(
        "ix_applications_user_status", "applications", ["user_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_applications_user_status")
    op.drop_table("applications")
