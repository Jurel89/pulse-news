"""add generation and delivery profiles

Revision ID: 4c5d6e7f8091
Revises: 3b4c5d6e7f80
Create Date: 2026-04-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "4c5d6e7f8091"
down_revision = "3b4c5d6e7f80"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "generation_profiles" not in table_names:
        op.create_table(
            "generation_profiles",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("provider_id", sa.Integer(), nullable=True),
            sa.Column(
                "model_name", sa.String(length=255), nullable=False, server_default=""
            ),
            sa.Column(
                "api_key_binding_mode",
                sa.String(length=32),
                nullable=False,
                server_default="pinned_key",
            ),
            sa.Column("api_key_id", sa.Integer(), nullable=True),
            sa.Column("settings_json", sa.Text(), nullable=True),
            sa.Column(
                "is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["provider_id"], ["providers.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["api_key_id"], ["api_keys.id"], ondelete="SET NULL"
            ),
        )
        op.create_index(
            "ix_generation_profiles_provider_id", "generation_profiles", ["provider_id"]
        )
        op.create_index(
            "ix_generation_profiles_api_key_id", "generation_profiles", ["api_key_id"]
        )

    if "delivery_profiles" not in table_names:
        op.create_table(
            "delivery_profiles",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column(
                "provider_type",
                sa.String(length=64),
                nullable=False,
                server_default="resend",
            ),
            sa.Column(
                "api_key_binding_mode",
                sa.String(length=32),
                nullable=False,
                server_default="pinned_key",
            ),
            sa.Column("api_key_id", sa.Integer(), nullable=True),
            sa.Column("from_email", sa.String(length=320), nullable=True),
            sa.Column("reply_to", sa.String(length=320), nullable=True),
            sa.Column("delivery_tags_json", sa.Text(), nullable=True),
            sa.Column(
                "is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["api_key_id"], ["api_keys.id"], ondelete="SET NULL"
            ),
        )
        op.create_index(
            "ix_delivery_profiles_api_key_id", "delivery_profiles", ["api_key_id"]
        )

    newsletter_columns = _column_names(inspector, "newsletters")
    with op.batch_alter_table("newsletters") as batch_op:
        if "generation_profile_id" not in newsletter_columns:
            batch_op.add_column(
                sa.Column("generation_profile_id", sa.Integer(), nullable=True)
            )
        if "delivery_profile_id" not in newsletter_columns:
            batch_op.add_column(
                sa.Column("delivery_profile_id", sa.Integer(), nullable=True)
            )
        batch_op.create_foreign_key(
            "fk_newsletters_generation_profile_id",
            "generation_profiles",
            ["generation_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_newsletters_delivery_profile_id",
            "delivery_profiles",
            ["delivery_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    newsletter_columns = _column_names(inspector, "newsletters")

    with op.batch_alter_table("newsletters") as batch_op:
        batch_op.drop_constraint(
            "fk_newsletters_generation_profile_id", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_newsletters_delivery_profile_id", type_="foreignkey"
        )
        if "generation_profile_id" in newsletter_columns:
            batch_op.drop_column("generation_profile_id")
        if "delivery_profile_id" in newsletter_columns:
            batch_op.drop_column("delivery_profile_id")

    if "generation_profiles" in set(inspector.get_table_names()):
        op.drop_index(
            "ix_generation_profiles_api_key_id", table_name="generation_profiles"
        )
        op.drop_index(
            "ix_generation_profiles_provider_id", table_name="generation_profiles"
        )
        op.drop_table("generation_profiles")

    if "delivery_profiles" in set(inspector.get_table_names()):
        op.drop_index("ix_delivery_profiles_api_key_id", table_name="delivery_profiles")
        op.drop_table("delivery_profiles")
