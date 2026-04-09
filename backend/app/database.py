from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


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


def init_database() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
