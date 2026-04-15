"""add revision generation metadata

Revision ID: 7f8091a2b3c4
Revises: 6e7f8091a2b3
Create Date: 2026-04-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "7f8091a2b3c4"
down_revision = "6e7f8091a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "draft_revisions" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("draft_revisions")}
    with op.batch_alter_table("draft_revisions") as batch_op:
        if "provider_snapshot_json" not in columns:
            batch_op.add_column(
                sa.Column("provider_snapshot_json", sa.Text(), nullable=True)
            )
        if "token_usage_json" not in columns:
            batch_op.add_column(sa.Column("token_usage_json", sa.Text(), nullable=True))
        if "raw_response_hash" not in columns:
            batch_op.add_column(
                sa.Column("raw_response_hash", sa.String(length=128), nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "draft_revisions" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("draft_revisions")}
    with op.batch_alter_table("draft_revisions") as batch_op:
        if "provider_snapshot_json" in columns:
            batch_op.drop_column("provider_snapshot_json")
        if "token_usage_json" in columns:
            batch_op.drop_column("token_usage_json")
        if "raw_response_hash" in columns:
            batch_op.drop_column("raw_response_hash")
