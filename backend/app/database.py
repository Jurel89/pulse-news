from __future__ import annotations

import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    return create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )


@lru_cache(maxsize=1)
def get_session_maker():
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False, class_=Session)


def get_db_session() -> Iterator[Session]:
    session = get_session_maker()()
    try:
        yield session
    finally:
        session.close()


_MIGRATIONS = [
    (
        "newsletter_runs",
        "attempt_key",
        "ALTER TABLE newsletter_runs ADD COLUMN attempt_key VARCHAR(255)",
    ),
    (
        "newsletter_runs",
        "started_at",
        "ALTER TABLE newsletter_runs ADD COLUMN started_at DATETIME",
    ),
    (
        "newsletter_runs",
        "completed_at",
        "ALTER TABLE newsletter_runs ADD COLUMN completed_at DATETIME",
    ),
    (
        "newsletter_runs",
        "failure_reason",
        "ALTER TABLE newsletter_runs ADD COLUMN failure_reason TEXT",
    ),
    (
        "newsletter_runs",
        "rendered_subject",
        "ALTER TABLE newsletter_runs ADD COLUMN rendered_subject VARCHAR(255)",
    ),
    (
        "newsletter_runs",
        "rendered_preheader",
        "ALTER TABLE newsletter_runs ADD COLUMN rendered_preheader VARCHAR(255)",
    ),
    (
        "newsletter_runs",
        "rendered_html",
        "ALTER TABLE newsletter_runs ADD COLUMN rendered_html TEXT",
    ),
    (
        "newsletter_runs",
        "rendered_plain_text",
        "ALTER TABLE newsletter_runs ADD COLUMN rendered_plain_text TEXT",
    ),
    (
        "newsletter_runs",
        "snapshot_prompt",
        "ALTER TABLE newsletter_runs ADD COLUMN snapshot_prompt TEXT",
    ),
    (
        "newsletter_runs",
        "snapshot_newsletter_name",
        "ALTER TABLE newsletter_runs ADD COLUMN snapshot_newsletter_name VARCHAR(255)",
    ),
    (
        "newsletter_runs",
        "snapshot_newsletter_slug",
        "ALTER TABLE newsletter_runs ADD COLUMN snapshot_newsletter_slug VARCHAR(255)",
    ),
    (
        "newsletter_runs",
        "snapshot_delivery_topic",
        "ALTER TABLE newsletter_runs ADD COLUMN snapshot_delivery_topic VARCHAR(255)",
    ),
    (
        "newsletter_runs",
        "snapshot_status_at_run",
        "ALTER TABLE newsletter_runs ADD COLUMN snapshot_status_at_run VARCHAR(32)",
    ),
    (
        "newsletters",
        "deleted_at",
        "ALTER TABLE newsletters ADD COLUMN deleted_at DATETIME",
    ),
    (
        "newsletter_recipients",
        "status",
        "ALTER TABLE newsletter_recipients ADD COLUMN status VARCHAR(32) DEFAULT 'subscribed'",
    ),
]


def _run_schema_migrations(engine) -> None:
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    for table_name, column_name, alter_sql in _MIGRATIONS:
        if table_name not in existing_tables:
            continue
        existing_columns = {col["name"] for col in insp.get_columns(table_name)}
        if column_name not in existing_columns:
            try:
                with engine.begin() as conn:
                    conn.execute(text(alter_sql))
                logger.info("Migrated: added column %s.%s", table_name, column_name)
            except Exception:
                logger.warning("Migration failed for %s.%s", table_name, column_name)


def init_database() -> None:
    from app import models  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _run_schema_migrations(engine)
