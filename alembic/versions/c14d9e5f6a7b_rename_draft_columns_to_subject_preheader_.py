"""rename draft columns to subject preheader body_text

Revision ID: c14d9e5f6a7b
Revises: ab13d7e4f9c2
Create Date: 2026-04-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "c14d9e5f6a7b"
down_revision = "ab13d7e4f9c2"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    newsletter_columns = _column_names(inspector, "newsletters")

    with op.batch_alter_table(
        "newsletters",
        schema=None,
        recreate="always",
    ) as batch_op:
        if "draft_subject" in newsletter_columns:
            batch_op.alter_column("draft_subject", new_column_name="subject")
        if "draft_preheader" in newsletter_columns:
            batch_op.alter_column("draft_preheader", new_column_name="preheader")
        if "draft_body_text" in newsletter_columns:
            batch_op.alter_column("draft_body_text", new_column_name="body_text")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    newsletter_columns = _column_names(inspector, "newsletters")

    with op.batch_alter_table(
        "newsletters",
        schema=None,
        recreate="always",
    ) as batch_op:
        if "subject" in newsletter_columns:
            batch_op.alter_column("subject", new_column_name="draft_subject")
        if "preheader" in newsletter_columns:
            batch_op.alter_column("preheader", new_column_name="draft_preheader")
        if "body_text" in newsletter_columns:
            batch_op.alter_column("body_text", new_column_name="draft_body_text")
