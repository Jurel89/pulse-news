"""simplify newsletter schema

Revision ID: ab13d7e4f9c2
Revises: 9b0c1d2e3f4a
Create Date: 2026-04-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "ab13d7e4f9c2"
down_revision = "9b0c1d2e3f4a"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _foreign_key_names(inspector, table_name: str) -> set[str | None]:
    return {
        foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name)
    }


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _table_names(inspector) -> set[str]:
    return set(inspector.get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    newsletter_columns = _column_names(inspector, "newsletters")
    tables = _table_names(inspector)

    if "draft_revisions" in tables and "draft_head_revision_id" in newsletter_columns:
        bind.execute(
            sa.text(
                """
                UPDATE newsletters
                SET subject = COALESCE(
                    (
                        SELECT draft_revisions.subject
                        FROM draft_revisions
                        WHERE draft_revisions.id = newsletters.draft_head_revision_id
                    ),
                    (
                        SELECT draft_revisions.subject
                        FROM draft_revisions
                        WHERE draft_revisions.id = newsletters.approved_revision_id
                    ),
                    subject
                ),
                preheader = COALESCE(
                    (
                        SELECT draft_revisions.preheader
                        FROM draft_revisions
                        WHERE draft_revisions.id = newsletters.draft_head_revision_id
                    ),
                    (
                        SELECT draft_revisions.preheader
                        FROM draft_revisions
                        WHERE draft_revisions.id = newsletters.approved_revision_id
                    ),
                    preheader
                ),
                body_text = COALESCE(
                    (
                        SELECT draft_revisions.body_text
                        FROM draft_revisions
                        WHERE draft_revisions.id = newsletters.draft_head_revision_id
                    ),
                    (
                        SELECT draft_revisions.body_text
                        FROM draft_revisions
                        WHERE draft_revisions.id = newsletters.approved_revision_id
                    ),
                    body_text
                )
                WHERE draft_head_revision_id IS NOT NULL OR approved_revision_id IS NOT NULL
                """
            )
        )

    if "from_email" not in newsletter_columns:
        with op.batch_alter_table(
            "newsletters",
            schema=None,
            recreate="always",
        ) as batch_op:
            batch_op.add_column(
                sa.Column("from_email", sa.String(length=320), nullable=True)
            )

    if "delivery_profiles" in tables and "delivery_profile_id" in newsletter_columns:
        bind.execute(
            sa.text(
                """
                UPDATE newsletters
                SET from_email = COALESCE(
                    from_email,
                    (
                        SELECT delivery_profiles.from_email
                        FROM delivery_profiles
                        WHERE delivery_profiles.id = newsletters.delivery_profile_id
                    )
                )
                WHERE delivery_profile_id IS NOT NULL
                """
            )
        )

    inspector = sa.inspect(bind)
    newsletter_columns = _column_names(inspector, "newsletters")
    newsletter_foreign_keys = _foreign_key_names(inspector, "newsletters")
    with op.batch_alter_table(
        "newsletters",
        schema=None,
        recreate="always",
    ) as batch_op:
        if "fk_newsletters_approved_revision_id" in newsletter_foreign_keys:
            batch_op.drop_constraint(
                "fk_newsletters_approved_revision_id", type_="foreignkey"
            )
        if "fk_newsletters_draft_head_revision_id" in newsletter_foreign_keys:
            batch_op.drop_constraint(
                "fk_newsletters_draft_head_revision_id", type_="foreignkey"
            )
        if "fk_newsletters_generation_profile_id" in newsletter_foreign_keys:
            batch_op.drop_constraint(
                "fk_newsletters_generation_profile_id", type_="foreignkey"
            )
        if "fk_newsletters_delivery_profile_id" in newsletter_foreign_keys:
            batch_op.drop_constraint(
                "fk_newsletters_delivery_profile_id", type_="foreignkey"
            )
        if "approved_revision_id" in newsletter_columns:
            batch_op.drop_column("approved_revision_id")
        if "draft_head_revision_id" in newsletter_columns:
            batch_op.drop_column("draft_head_revision_id")
        if "generation_profile_id" in newsletter_columns:
            batch_op.drop_column("generation_profile_id")
        if "delivery_profile_id" in newsletter_columns:
            batch_op.drop_column("delivery_profile_id")
        if "version" in newsletter_columns:
            batch_op.drop_column("version")

    inspector = sa.inspect(bind)
    run_columns = _column_names(inspector, "newsletter_runs")
    run_foreign_keys = _foreign_key_names(inspector, "newsletter_runs")
    with op.batch_alter_table(
        "newsletter_runs",
        schema=None,
        recreate="always",
    ) as batch_op:
        if "fk_newsletter_runs_revision_id" in run_foreign_keys:
            batch_op.drop_constraint(
                "fk_newsletter_runs_revision_id", type_="foreignkey"
            )
        if "revision_id" in run_columns:
            batch_op.drop_column("revision_id")

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "draft_revisions" in tables:
        draft_revision_indexes = _index_names(inspector, "draft_revisions")
        if "ix_draft_revisions_generation_run_id" in draft_revision_indexes:
            op.drop_index(
                "ix_draft_revisions_generation_run_id", table_name="draft_revisions"
            )
        if "ix_draft_revisions_state" in draft_revision_indexes:
            op.drop_index("ix_draft_revisions_state", table_name="draft_revisions")
        if "ix_draft_revisions_newsletter_id" in draft_revision_indexes:
            op.drop_index(
                "ix_draft_revisions_newsletter_id", table_name="draft_revisions"
            )
        op.drop_table("draft_revisions")

    if "generation_profiles" in tables:
        generation_profile_indexes = _index_names(inspector, "generation_profiles")
        if "ix_generation_profiles_api_key_id" in generation_profile_indexes:
            op.drop_index(
                "ix_generation_profiles_api_key_id", table_name="generation_profiles"
            )
        if "ix_generation_profiles_provider_id" in generation_profile_indexes:
            op.drop_index(
                "ix_generation_profiles_provider_id", table_name="generation_profiles"
            )
        op.drop_table("generation_profiles")

    if "delivery_profiles" in tables:
        delivery_profile_indexes = _index_names(inspector, "delivery_profiles")
        if "ix_delivery_profiles_api_key_id" in delivery_profile_indexes:
            op.drop_index(
                "ix_delivery_profiles_api_key_id", table_name="delivery_profiles"
            )
        op.drop_table("delivery_profiles")


def downgrade() -> None:
    bind = op.get_bind()

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
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_generation_profiles_provider_id", "generation_profiles", ["provider_id"]
    )
    op.create_index(
        "ix_generation_profiles_api_key_id", "generation_profiles", ["api_key_id"]
    )

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
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_delivery_profiles_api_key_id", "delivery_profiles", ["api_key_id"]
    )

    op.create_table(
        "draft_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("newsletter_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("preheader", sa.String(length=255), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("prompt_snapshot", sa.Text(), nullable=True),
        sa.Column("source_bundle_snapshot_json", sa.Text(), nullable=True),
        sa.Column("created_by_email", sa.String(length=320), nullable=True),
        sa.Column("provider_snapshot_json", sa.Text(), nullable=True),
        sa.Column("token_usage_json", sa.Text(), nullable=True),
        sa.Column("raw_response_hash", sa.String(length=128), nullable=True),
        sa.Column("highlights_json", sa.Text(), nullable=True),
        sa.Column("source_references_json", sa.Text(), nullable=True),
        sa.Column("generation_run_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.ForeignKeyConstraint(["newsletter_id"], ["newsletters.id"]),
        sa.ForeignKeyConstraint(
            ["generation_run_id"],
            ["newsletter_runs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "newsletter_id", "version_number", name="uq_draft_revision_version"
        ),
    )
    op.create_index(
        "ix_draft_revisions_newsletter_id", "draft_revisions", ["newsletter_id"]
    )
    op.create_index("ix_draft_revisions_state", "draft_revisions", ["state"])
    op.create_index(
        "ix_draft_revisions_generation_run_id",
        "draft_revisions",
        ["generation_run_id"],
    )

    with op.batch_alter_table(
        "newsletters",
        schema=None,
        recreate="always",
    ) as batch_op:
        batch_op.add_column(
            sa.Column("approved_revision_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("draft_head_revision_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("generation_profile_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("delivery_profile_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("version", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.drop_column("from_email")

    with op.batch_alter_table(
        "newsletter_runs",
        schema=None,
        recreate="always",
    ) as batch_op:
        batch_op.add_column(sa.Column("revision_id", sa.Integer(), nullable=True))

    newsletters = bind.execute(
        sa.text(
            "SELECT id, prompt, subject, preheader, body_text FROM newsletters ORDER BY id"
        )
    ).mappings()

    for newsletter in newsletters:
        inserted_revision_id = bind.execute(
            sa.text(
                """
                INSERT INTO draft_revisions (
                    newsletter_id,
                    version_number,
                    state,
                    origin,
                    subject,
                    preheader,
                    body_text,
                    prompt_snapshot,
                    version
                )
                VALUES (
                    :newsletter_id,
                    1,
                    'approved',
                    'imported',
                    :subject,
                    :preheader,
                    :body_text,
                    :prompt_snapshot,
                    1
                )
                """
            ),
            {
                "newsletter_id": newsletter["id"],
                "subject": newsletter["subject"] or "",
                "preheader": newsletter["preheader"],
                "body_text": newsletter["body_text"] or "",
                "prompt_snapshot": newsletter["prompt"],
            },
        ).lastrowid

        bind.execute(
            sa.text(
                """
                UPDATE newsletters
                SET approved_revision_id = :revision_id,
                    draft_head_revision_id = :revision_id,
                    version = COALESCE(version, 1)
                WHERE id = :newsletter_id
                """
            ),
            {
                "newsletter_id": newsletter["id"],
                "revision_id": inserted_revision_id,
            },
        )

    with op.batch_alter_table(
        "newsletters",
        schema=None,
        recreate="always",
    ) as batch_op:
        batch_op.create_foreign_key(
            "fk_newsletters_approved_revision_id",
            "draft_revisions",
            ["approved_revision_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_newsletters_draft_head_revision_id",
            "draft_revisions",
            ["draft_head_revision_id"],
            ["id"],
            ondelete="SET NULL",
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

    with op.batch_alter_table(
        "newsletter_runs",
        schema=None,
        recreate="always",
    ) as batch_op:
        batch_op.create_foreign_key(
            "fk_newsletter_runs_revision_id",
            "draft_revisions",
            ["revision_id"],
            ["id"],
            ondelete="SET NULL",
        )
