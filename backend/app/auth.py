from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import SystemSettings, User, utc_now

SYSTEM_SETTINGS_ID = 1


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_system_settings(session: Session) -> SystemSettings | None:
    return session.get(SystemSettings, SYSTEM_SETTINGS_ID)


def create_system_settings(session: Session) -> SystemSettings:
    settings = SystemSettings(id=SYSTEM_SETTINGS_ID)
    session.add(settings)
    session.flush()
    return settings


def get_or_create_system_settings(session: Session) -> SystemSettings:
    settings = get_system_settings(session)
    if settings is None:
        settings = create_system_settings(session)
    return settings


def get_operator_count(session: Session) -> int:
    return session.scalar(select(func.count(User.id))) or 0


def bootstrap_enabled(session: Session) -> bool:
    settings = get_system_settings(session)
    if settings is None:
        return True
    return not settings.bootstrap_disabled_at


def claim_bootstrap(session: Session) -> None:
    settings = get_or_create_system_settings(session)
    settings.initialized = True
    settings.bootstrap_disabled_at = utc_now()
    session.add(settings)
    session.flush()


def mark_bootstrap_complete(session: Session, user_id: int) -> None:
    settings = get_or_create_system_settings(session)
    settings.initialized = True
    session.add(settings)
    session.flush()


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == normalize_email(email)))


def set_authenticated_session(request: Request, user_id: int, email: str) -> None:
    request.session["user_id"] = user_id
    request.session["email"] = email


def clear_authenticated_session(request: Request) -> None:
    request.session.pop("user_id", None)
    request.session.pop("email", None)


def get_authenticated_user(request: Request, db: Session | None = None) -> User | None:
    user_id = request.session.get("user_id")
    email = request.session.get("email")
    if user_id is None or email is None:
        return None
    if db is None:
        from app.database import get_session_maker

        session = get_session_maker()()
        try:
            return get_user_by_email(session, email)
        finally:
            session.close()
    return get_user_by_email(db, email)


def require_authenticated_user(request: Request, db: Session) -> User:
    user = get_authenticated_user(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return user
