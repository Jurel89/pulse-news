"""add email templates, providers, and api keys

Revision ID: bb2893350268
Revises: 1703f317ccfa
Create Date: 2026-04-11 17:46:48.891258

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bb2893350268"
down_revision = "1703f317ccfa"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_names(inspector, table_name: str) -> set[str]:
    if not _table_exists(inspector, table_name):
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _foreign_key_names(inspector, table_name: str) -> set[str]:
    return {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys(table_name)
        if foreign_key.get("name")
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "api_keys"):
        op.create_table(
            "api_keys",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("provider_type", sa.String(length=64), nullable=False),
            sa.Column("key_value", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    api_key_indexes = _index_names(inspector, "api_keys")
    if op.f("ix_api_keys_id") not in api_key_indexes:
        op.create_index(op.f("ix_api_keys_id"), "api_keys", ["id"], unique=False)
    if op.f("ix_api_keys_provider_type") not in api_key_indexes:
        op.create_index(
            op.f("ix_api_keys_provider_type"),
            "api_keys",
            ["provider_type"],
            unique=False,
        )

    if not _table_exists(inspector, "email_templates"):
        op.create_table(
            "email_templates",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("html_template", sa.Text(), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False),
            sa.Column("is_system", sa.Boolean(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    email_template_indexes = _index_names(inspector, "email_templates")
    if op.f("ix_email_templates_id") not in email_template_indexes:
        op.create_index(op.f("ix_email_templates_id"), "email_templates", ["id"], unique=False)
    if op.f("ix_email_templates_key") not in email_template_indexes:
        op.create_index(op.f("ix_email_templates_key"), "email_templates", ["key"], unique=True)

    if not _table_exists(inspector, "providers"):
        op.create_table(
            "providers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("provider_type", sa.String(length=64), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("default_model", sa.String(length=255), nullable=True),
            sa.Column("configuration", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    provider_indexes = _index_names(inspector, "providers")
    if op.f("ix_providers_id") not in provider_indexes:
        op.create_index(op.f("ix_providers_id"), "providers", ["id"], unique=False)
    if op.f("ix_providers_provider_type") not in provider_indexes:
        op.create_index(
            op.f("ix_providers_provider_type"),
            "providers",
            ["provider_type"],
            unique=False,
        )

    newsletter_columns = _column_names(inspector, "newsletters")
    newsletter_indexes = _index_names(inspector, "newsletters")
    newsletter_foreign_keys = _foreign_key_names(inspector, "newsletters")

    with op.batch_alter_table("newsletters") as batch_op:
        if "provider_id" not in newsletter_columns:
            batch_op.add_column(sa.Column("provider_id", sa.Integer(), nullable=True))
        if "template_id" not in newsletter_columns:
            batch_op.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        if "api_key_id" not in newsletter_columns:
            batch_op.add_column(sa.Column("api_key_id", sa.Integer(), nullable=True))

        if "fk_newsletters_provider_id" not in newsletter_foreign_keys:
            batch_op.create_foreign_key(
                "fk_newsletters_provider_id",
                "providers",
                ["provider_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "fk_newsletters_template_id" not in newsletter_foreign_keys:
            batch_op.create_foreign_key(
                "fk_newsletters_template_id",
                "email_templates",
                ["template_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "fk_newsletters_api_key_id" not in newsletter_foreign_keys:
            batch_op.create_foreign_key(
                "fk_newsletters_api_key_id",
                "api_keys",
                ["api_key_id"],
                ["id"],
                ondelete="SET NULL",
            )

        if op.f("ix_newsletters_api_key_id") not in newsletter_indexes:
            batch_op.create_index(op.f("ix_newsletters_api_key_id"), ["api_key_id"], unique=False)
        if op.f("ix_newsletters_provider_id") not in newsletter_indexes:
            batch_op.create_index(op.f("ix_newsletters_provider_id"), ["provider_id"], unique=False)
        if op.f("ix_newsletters_template_id") not in newsletter_indexes:
            batch_op.create_index(op.f("ix_newsletters_template_id"), ["template_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("newsletters") as batch_op:
        batch_op.drop_index(op.f("ix_newsletters_template_id"))
        batch_op.drop_index(op.f("ix_newsletters_provider_id"))
        batch_op.drop_index(op.f("ix_newsletters_api_key_id"))
        batch_op.drop_constraint("fk_newsletters_api_key_id", type_="foreignkey")
        batch_op.drop_constraint("fk_newsletters_template_id", type_="foreignkey")
        batch_op.drop_constraint("fk_newsletters_provider_id", type_="foreignkey")
        batch_op.drop_column("api_key_id")
        batch_op.drop_column("template_id")
        batch_op.drop_column("provider_id")

    op.drop_index(op.f("ix_providers_provider_type"), table_name="providers")
    op.drop_index(op.f("ix_providers_id"), table_name="providers")
    op.drop_table("providers")

    op.drop_index(op.f("ix_email_templates_key"), table_name="email_templates")
    op.drop_index(op.f("ix_email_templates_id"), table_name="email_templates")
    op.drop_table("email_templates")

    op.drop_index(op.f("ix_api_keys_provider_type"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_id"), table_name="api_keys")
    op.drop_table("api_keys")
