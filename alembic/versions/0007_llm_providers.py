"""Add user_llm_providers table, migrate hf_token_encrypted into it

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_llm_providers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("api_key_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "user_id", "provider", name="uq_user_llm_providers_user_provider"
        ),
    )
    op.execute(
        "INSERT INTO user_llm_providers (user_id, provider, api_key_encrypted, sort_order) "
        "SELECT user_id, 'huggingface', hf_token_encrypted, 0 "
        "FROM user_settings WHERE hf_token_encrypted IS NOT NULL"
    )
    op.drop_column("user_settings", "hf_token_encrypted")


def downgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("hf_token_encrypted", sa.LargeBinary, nullable=True),
    )
    op.execute(
        "UPDATE user_settings s SET hf_token_encrypted = p.api_key_encrypted "
        "FROM user_llm_providers p "
        "WHERE p.user_id = s.user_id AND p.provider = 'huggingface'"
    )
    op.drop_table("user_llm_providers")
