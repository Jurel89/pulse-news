"""add resend api key to newsletters

Revision ID: 1c2b6170f8d3
Revises: bb2893350268
Create Date: 2026-04-11 19:05:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1c2b6170f8d3"
down_revision = "bb2893350268"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_key_names(inspector, table_name: str) -> set[str]:
    return {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys(table_name)
        if foreign_key.get("name")
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    newsletter_columns = _column_names(inspector, "newsletters")
    newsletter_indexes = _index_names(inspector, "newsletters")
    newsletter_foreign_keys = _foreign_key_names(inspector, "newsletters")

    with op.batch_alter_table("newsletters") as batch_op:
        if "resend_api_key_id" not in newsletter_columns:
            batch_op.add_column(
                sa.Column("resend_api_key_id", sa.Integer(), nullable=True)
            )

        if "fk_newsletters_resend_api_key_id" not in newsletter_foreign_keys:
            batch_op.create_foreign_key(
                "fk_newsletters_resend_api_key_id",
                "api_keys",
                ["resend_api_key_id"],
                ["id"],
                ondelete="SET NULL",
            )

        if op.f("ix_newsletters_resend_api_key_id") not in newsletter_indexes:
            batch_op.create_index(
                op.f("ix_newsletters_resend_api_key_id"),
                ["resend_api_key_id"],
                unique=False,
            )


def downgrade() -> None:
    with op.batch_alter_table("newsletters") as batch_op:
        batch_op.drop_index(op.f("ix_newsletters_resend_api_key_id"))
        batch_op.drop_constraint("fk_newsletters_resend_api_key_id", type_="foreignkey")
        batch_op.drop_column("resend_api_key_id")
