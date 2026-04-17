"""add oauth columns to api_keys

Revision ID: d1e2f3a4b5c6
Revises: c14d9e5f6a7b
Create Date: 2026-04-17 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d1e2f3a4b5c6"
down_revision = "c14d9e5f6a7b"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = _column_names(inspector, "api_keys")

    with op.batch_alter_table("api_keys", schema=None, recreate="always") as batch_op:
        if "auth_type" not in existing:
            batch_op.add_column(
                sa.Column(
                    "auth_type",
                    sa.String(length=32),
                    nullable=False,
                    server_default="api_key",
                )
            )
        if "oauth_refresh_token" not in existing:
            batch_op.add_column(
                sa.Column("oauth_refresh_token", sa.Text(), nullable=True)
            )
        if "oauth_access_token" not in existing:
            batch_op.add_column(
                sa.Column("oauth_access_token", sa.Text(), nullable=True)
            )
        if "oauth_expires_at" not in existing:
            batch_op.add_column(
                sa.Column("oauth_expires_at", sa.DateTime(timezone=True), nullable=True)
            )
        if "oauth_account_id" not in existing:
            batch_op.add_column(
                sa.Column("oauth_account_id", sa.String(length=255), nullable=True)
            )
        if "oauth_plan_type" not in existing:
            batch_op.add_column(
                sa.Column("oauth_plan_type", sa.String(length=64), nullable=True)
            )
        if "oauth_metadata_json" not in existing:
            batch_op.add_column(
                sa.Column("oauth_metadata_json", sa.Text(), nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = _column_names(inspector, "api_keys")

    with op.batch_alter_table("api_keys", schema=None, recreate="always") as batch_op:
        for col in (
            "oauth_metadata_json",
            "oauth_plan_type",
            "oauth_account_id",
            "oauth_expires_at",
            "oauth_access_token",
            "oauth_refresh_token",
            "auth_type",
        ):
            if col in existing:
                batch_op.drop_column(col)
