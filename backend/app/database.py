from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
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


def _repair_invalid_provider_state(session: Session) -> None:
    from app.models import ApiKey, Provider

    providers = session.scalars(select(Provider).where(Provider.is_enabled.is_(True))).all()
    disabled_count = 0

    for provider in providers:
        where_clause = [
            ApiKey.provider_type == provider.provider_type,
            ApiKey.is_active.is_(True),
        ]
        if provider.provider_type == "openai_chatgpt":
            where_clause.append(ApiKey.auth_type == "oauth")
        has_active_key = session.scalar(select(ApiKey).where(*where_clause)) is not None

        if not has_active_key:
            provider.is_enabled = False
            session.add(provider)
            disabled_count += 1
            logger.warning(
                f"Disabled provider '{provider.name}' (id={provider.id}) "
                f"because no active API key exists for type "
                f"'{provider.provider_type}'"
            )

    if disabled_count > 0:
        session.commit()
        logger.info(f"Disabled {disabled_count} provider(s) due to missing API keys")


def _ensure_system_settings_row(session: Session) -> None:
    from app.auth import get_or_create_system_settings

    get_or_create_system_settings(session)
    session.commit()


def _disable_legacy_chatgpt_manual_keys(session: Session) -> None:
    from app.models import ApiKey

    legacy = session.scalars(
        select(ApiKey).where(
            ApiKey.provider_type == "openai_chatgpt",
            ApiKey.auth_type == "api_key",
            ApiKey.is_active.is_(True),
        )
    ).all()
    for key in legacy:
        key.is_active = False
        session.add(key)
        logger.warning(
            f"Disabled legacy manual API key '{key.name}' (id={key.id}) for "
            f"openai_chatgpt — ChatGPT subscription requires OAuth."
        )
    if legacy:
        session.commit()
        logger.info(f"Disabled {len(legacy)} legacy ChatGPT manual key(s)")


def _repair_legacy_chatgpt_models(session: Session) -> None:
    from app.models import Newsletter, Provider
    from app.oauth.openai_chatgpt import CHATGPT_DEFAULT_MODEL, CHATGPT_SUPPORTED_MODELS

    repaired_providers = 0
    providers = session.scalars(
        select(Provider).where(Provider.provider_type == "openai_chatgpt")
    ).all()
    for provider in providers:
        if provider.default_model and provider.default_model not in CHATGPT_SUPPORTED_MODELS:
            old_model = provider.default_model
            provider.default_model = CHATGPT_DEFAULT_MODEL
            session.add(provider)
            repaired_providers += 1
            logger.warning(
                f"Repaired provider '{provider.name}' (id={provider.id}) model "
                f"from '{old_model}' to '{CHATGPT_DEFAULT_MODEL}'"
            )

    repaired_newsletters = 0
    newsletters = session.scalars(
        select(Newsletter).where(Newsletter.provider_name == "openai_chatgpt")
    ).all()
    for newsletter in newsletters:
        if newsletter.model_name and newsletter.model_name not in CHATGPT_SUPPORTED_MODELS:
            old_model = newsletter.model_name
            newsletter.model_name = CHATGPT_DEFAULT_MODEL
            session.add(newsletter)
            repaired_newsletters += 1
            logger.warning(
                f"Repaired newsletter '{newsletter.name}' (id={newsletter.id}) model "
                f"from '{old_model}' to '{CHATGPT_DEFAULT_MODEL}'"
            )

    if repaired_providers or repaired_newsletters:
        session.commit()
        logger.info(
            f"Repaired {repaired_providers} provider(s) and "
            f"{repaired_newsletters} newsletter(s) with legacy ChatGPT models"
        )


def _disable_broken_chatgpt_oauth_rows(session: Session) -> None:
    from app.models import ApiKey

    broken = session.scalars(
        select(ApiKey).where(
            ApiKey.provider_type == "openai_chatgpt",
            ApiKey.auth_type == "oauth",
            ApiKey.is_active.is_(True),
        )
    ).all()
    disabled_count = 0
    for key in broken:
        has_refresh = bool(key.oauth_refresh_token and key.oauth_refresh_token.strip())
        if not has_refresh:
            key.is_active = False
            session.add(key)
            disabled_count += 1
            logger.warning(
                f"Disabled broken ChatGPT OAuth connection '{key.name}' (id={key.id}) "
                f"because it has no refresh token and cannot be refreshed."
            )
    if disabled_count:
        session.commit()
        logger.info(f"Disabled {disabled_count} broken ChatGPT OAuth connection(s)")


def init_database() -> None:
    get_settings()

    with _project_root_working_directory():
        command.upgrade(_get_alembic_config(), "head")

    with get_session_maker()() as session:
        _disable_legacy_chatgpt_manual_keys(session)
        _disable_broken_chatgpt_oauth_rows(session)
        _repair_legacy_chatgpt_models(session)
        _repair_invalid_provider_state(session)
        _ensure_system_settings_row(session)
