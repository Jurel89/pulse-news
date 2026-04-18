"""add created by email to draft revisions

Revision ID: 6e7f8091a2b3
Revises: 5d6e7f8091a2
Create Date: 2026-04-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "6e7f8091a2b3"
down_revision = "5d6e7f8091a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "draft_revisions" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("draft_revisions")}
    with op.batch_alter_table("draft_revisions") as batch_op:
        if "created_by_email" not in columns:
            batch_op.add_column(
                sa.Column("created_by_email", sa.String(length=320), nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "draft_revisions" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("draft_revisions")}
    with op.batch_alter_table("draft_revisions") as batch_op:
        if "created_by_email" in columns:
            batch_op.drop_column("created_by_email")
