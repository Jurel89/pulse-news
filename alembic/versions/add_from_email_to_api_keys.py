"""add from email to api keys

Revision ID: 2a3b4c5d6e7f
Revises: 1c2b6170f8d3
Create Date: 2026-04-12 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2a3b4c5d6e7f"
down_revision = "1c2b6170f8d3"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    api_key_columns = _column_names(inspector, "api_keys")

    with op.batch_alter_table("api_keys") as batch_op:
        if "from_email" not in api_key_columns:
            batch_op.add_column(
                sa.Column("from_email", sa.String(length=320), nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    api_key_columns = _column_names(inspector, "api_keys")

    with op.batch_alter_table("api_keys") as batch_op:
        if "from_email" in api_key_columns:
            batch_op.drop_column("from_email")
