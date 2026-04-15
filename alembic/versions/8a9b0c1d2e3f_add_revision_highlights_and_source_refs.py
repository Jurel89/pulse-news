"""add revision highlights and source references

Revision ID: 8a9b0c1d2e3f
Revises: 7f8091a2b3c4
Create Date: 2026-04-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "8a9b0c1d2e3f"
down_revision = "7f8091a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "draft_revisions" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("draft_revisions")}
    with op.batch_alter_table("draft_revisions") as batch_op:
        if "highlights_json" not in columns:
            batch_op.add_column(sa.Column("highlights_json", sa.Text(), nullable=True))
        if "source_references_json" not in columns:
            batch_op.add_column(
                sa.Column("source_references_json", sa.Text(), nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "draft_revisions" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("draft_revisions")}
    with op.batch_alter_table("draft_revisions") as batch_op:
        if "highlights_json" in columns:
            batch_op.drop_column("highlights_json")
        if "source_references_json" in columns:
            batch_op.drop_column("source_references_json")
