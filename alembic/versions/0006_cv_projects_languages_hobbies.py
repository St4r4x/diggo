"""Add user_projects, user_languages, user_hobbies CV tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_projects",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("lang", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False, server_default=""),
        sa.Column("stack", sa.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("desc", sa.Text, nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint("lang IN ('fr', 'en')", name="ck_user_projects_lang"),
    )
    op.create_index("ix_user_projects_user_lang", "user_projects", ["user_id", "lang"])

    op.create_table(
        "user_languages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("lang", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint("lang IN ('fr', 'en')", name="ck_user_languages_lang"),
    )
    op.create_index(
        "ix_user_languages_user_lang", "user_languages", ["user_id", "lang"]
    )

    op.create_table(
        "user_hobbies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("lang", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint("lang IN ('fr', 'en')", name="ck_user_hobbies_lang"),
    )
    op.create_index("ix_user_hobbies_user_lang", "user_hobbies", ["user_id", "lang"])


def downgrade() -> None:
    op.drop_table("user_hobbies")
    op.drop_table("user_languages")
    op.drop_table("user_projects")
