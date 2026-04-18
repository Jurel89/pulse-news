"""add source bundle snapshot to revisions

Revision ID: 5d6e7f8091a2
Revises: 4c5d6e7f8091
Create Date: 2026-04-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "5d6e7f8091a2"
down_revision = "4c5d6e7f8091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "draft_revisions" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("draft_revisions")}
    with op.batch_alter_table("draft_revisions") as batch_op:
        if "source_bundle_snapshot_json" not in columns:
            batch_op.add_column(
                sa.Column("source_bundle_snapshot_json", sa.Text(), nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "draft_revisions" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("draft_revisions")}
    with op.batch_alter_table("draft_revisions") as batch_op:
        if "source_bundle_snapshot_json" in columns:
            batch_op.drop_column("source_bundle_snapshot_json")
