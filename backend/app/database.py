from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import PROJECT_ROOT, get_settings

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


def _get_alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    return config


@contextmanager
def _project_root_working_directory() -> Iterator[None]:
    original_cwd = Path.cwd()
    try:
        os.chdir(PROJECT_ROOT)
        yield
    finally:
        os.chdir(original_cwd)


def init_database() -> None:
    get_settings()

    with _project_root_working_directory():
        command.upgrade(_get_alembic_config(), "head")
