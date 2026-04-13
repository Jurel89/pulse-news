"""add operation modes to system settings

Revision ID: 9b0c1d2e3f4a
Revises: 8a9b0c1d2e3f
Create Date: 2026-04-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "9b0c1d2e3f4a"
down_revision = "8a9b0c1d2e3f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("system_settings")}
    with op.batch_alter_table("system_settings") as batch_op:
        if "ai_generation_mode" not in columns:
            batch_op.add_column(
                sa.Column(
                    "ai_generation_mode",
                    sa.String(length=32),
                    nullable=False,
                    server_default="live",
                )
            )
        if "email_delivery_mode" not in columns:
            batch_op.add_column(
                sa.Column(
                    "email_delivery_mode",
                    sa.String(length=32),
                    nullable=False,
                    server_default="live",
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("system_settings")}
    with op.batch_alter_table("system_settings") as batch_op:
        if "email_delivery_mode" in columns:
            batch_op.drop_column("email_delivery_mode")
        if "ai_generation_mode" in columns:
            batch_op.drop_column("ai_generation_mode")
