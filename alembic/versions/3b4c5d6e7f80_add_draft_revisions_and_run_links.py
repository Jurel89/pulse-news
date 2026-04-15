"""add draft revisions and run links

Revision ID: 3b4c5d6e7f80
Revises: 2a3b4c5d6e7f
Create Date: 2026-04-13 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "3b4c5d6e7f80"
down_revision = "2a3b4c5d6e7f"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _foreign_key_names(inspector, table_name: str) -> set[str]:
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())
    if "draft_revisions" not in table_names:
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
                ["generation_run_id"], ["newsletter_runs.id"], ondelete="SET NULL"
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

    newsletter_columns = _column_names(inspector, "newsletters")
    with op.batch_alter_table("newsletters") as batch_op:
        if "approved_revision_id" not in newsletter_columns:
            batch_op.add_column(
                sa.Column("approved_revision_id", sa.Integer(), nullable=True)
            )
        if "draft_head_revision_id" not in newsletter_columns:
            batch_op.add_column(
                sa.Column("draft_head_revision_id", sa.Integer(), nullable=True)
            )
        if "version" not in newsletter_columns:
            batch_op.add_column(
                sa.Column("version", sa.Integer(), nullable=False, server_default="1")
            )

    run_columns = _column_names(inspector, "newsletter_runs")
    with op.batch_alter_table("newsletter_runs") as batch_op:
        if "revision_id" not in run_columns:
            batch_op.add_column(sa.Column("revision_id", sa.Integer(), nullable=True))
        if "run_type" not in run_columns:
            batch_op.add_column(
                sa.Column(
                    "run_type",
                    sa.String(length=32),
                    nullable=False,
                    server_default="delivery",
                )
            )

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    newsletter_columns = _column_names(inspector, "newsletters")

    if "draft_revisions" in tables:
        newsletter_foreign_keys = _foreign_key_names(inspector, "newsletters")
        with op.batch_alter_table("newsletters") as batch_op:
            if "fk_newsletters_approved_revision_id" not in newsletter_foreign_keys:
                batch_op.create_foreign_key(
                    "fk_newsletters_approved_revision_id",
                    "draft_revisions",
                    ["approved_revision_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if "fk_newsletters_draft_head_revision_id" not in newsletter_foreign_keys:
                batch_op.create_foreign_key(
                    "fk_newsletters_draft_head_revision_id",
                    "draft_revisions",
                    ["draft_head_revision_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

        run_foreign_keys = _foreign_key_names(inspector, "newsletter_runs")
        with op.batch_alter_table("newsletter_runs") as batch_op:
            if "fk_newsletter_runs_revision_id" not in run_foreign_keys:
                batch_op.create_foreign_key(
                    "fk_newsletter_runs_revision_id",
                    "draft_revisions",
                    ["revision_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

    if "draft_revisions" in tables and "draft_subject" in newsletter_columns:
        newsletters = bind.execute(
            sa.text(
                "SELECT id, prompt, draft_subject, draft_preheader, draft_body_text "
                "FROM newsletters ORDER BY id"
            )
        ).mappings()

        for newsletter in newsletters:
            existing_revision = bind.execute(
                sa.text(
                    "SELECT id FROM draft_revisions WHERE newsletter_id = :newsletter_id LIMIT 1"
                ),
                {"newsletter_id": newsletter["id"]},
            ).scalar()
            if existing_revision is not None:
                continue

            inserted_revision_id = bind.execute(
                sa.text(
                    "INSERT INTO draft_revisions (newsletter_id, version_number, state, origin, subject, preheader, body_text, prompt_snapshot, version) "
                    "VALUES (:newsletter_id, 1, 'approved', 'imported', :subject, :preheader, :body_text, :prompt_snapshot, 1)"
                ),
                {
                    "newsletter_id": newsletter["id"],
                    "subject": newsletter["draft_subject"] or "",
                    "preheader": newsletter["draft_preheader"],
                    "body_text": newsletter["draft_body_text"] or "",
                    "prompt_snapshot": newsletter["prompt"],
                },
            ).lastrowid

            bind.execute(
                sa.text(
                    "UPDATE newsletters SET approved_revision_id = :revision_id, draft_head_revision_id = :revision_id, version = COALESCE(version, 1) "
                    "WHERE id = :newsletter_id"
                ),
                {
                    "newsletter_id": newsletter["id"],
                    "revision_id": inserted_revision_id,
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    newsletter_foreign_keys = _foreign_key_names(inspector, "newsletters")
    with op.batch_alter_table("newsletters") as batch_op:
        if "fk_newsletters_approved_revision_id" in newsletter_foreign_keys:
            batch_op.drop_constraint(
                "fk_newsletters_approved_revision_id", type_="foreignkey"
            )
        if "fk_newsletters_draft_head_revision_id" in newsletter_foreign_keys:
            batch_op.drop_constraint(
                "fk_newsletters_draft_head_revision_id", type_="foreignkey"
            )

    run_foreign_keys = _foreign_key_names(inspector, "newsletter_runs")
    with op.batch_alter_table("newsletter_runs") as batch_op:
        if "fk_newsletter_runs_revision_id" in run_foreign_keys:
            batch_op.drop_constraint(
                "fk_newsletter_runs_revision_id", type_="foreignkey"
            )

    newsletter_columns = _column_names(inspector, "newsletters")
    with op.batch_alter_table("newsletters") as batch_op:
        if "approved_revision_id" in newsletter_columns:
            batch_op.drop_column("approved_revision_id")
        if "draft_head_revision_id" in newsletter_columns:
            batch_op.drop_column("draft_head_revision_id")
        if "version" in newsletter_columns:
            batch_op.drop_column("version")

    run_columns = _column_names(inspector, "newsletter_runs")
    with op.batch_alter_table("newsletter_runs") as batch_op:
        if "revision_id" in run_columns:
            batch_op.drop_column("revision_id")
        if "run_type" in run_columns:
            batch_op.drop_column("run_type")

    if "draft_revisions" in set(inspector.get_table_names()):
        op.drop_index(
            "ix_draft_revisions_generation_run_id", table_name="draft_revisions"
        )
        op.drop_index("ix_draft_revisions_state", table_name="draft_revisions")
        op.drop_index("ix_draft_revisions_newsletter_id", table_name="draft_revisions")
        op.drop_table("draft_revisions")
