from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.models import SystemSettings, User, utc_now


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_operator_count(session: Session) -> int:
    return session.scalar(select(func.count(User.id))) or 0


def bootstrap_enabled(session: Session) -> bool:
    settings = session.scalar(select(SystemSettings).where(SystemSettings.id == 1))
    if settings is not None and settings.initialized:
        return False
    return get_operator_count(session) == 0


def claim_bootstrap(session: Session) -> bool:
    """Atomically claim bootstrap. Returns True if this call won the race."""
    settings = session.scalar(select(SystemSettings).where(SystemSettings.id == 1))
    if settings is not None and settings.initialized:
        return False
    if get_operator_count(session) > 0:
        return False

    inserted = session.execute(
        insert(SystemSettings).values(id=1, initialized=True).prefix_with("OR IGNORE")
    )
    if (inserted.rowcount or 0) == 1:
        return True

    claimed = session.execute(
        update(SystemSettings)
        .where(SystemSettings.id == 1, SystemSettings.initialized.is_(False))
        .values(initialized=True)
    )
    return (claimed.rowcount or 0) == 1


def mark_bootstrap_complete(session: Session, user_id: int) -> None:
    settings = session.scalar(select(SystemSettings).where(SystemSettings.id == 1))
    if settings is None:
        settings = SystemSettings(id=1)
    settings.initialized = True
    settings.operator_user_id = user_id
    settings.bootstrap_disabled_at = utc_now()
    session.add(settings)


def get_user_by_email(session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == normalize_email(email))
    return session.scalar(statement)


def get_user_by_id(session: Session, user_id: int) -> User | None:
    statement = select(User).where(User.id == user_id)
    return session.scalar(statement)


def set_authenticated_session(request: Request, user: User) -> None:
    request.session["user_id"] = user.id
    request.session["user_email"] = user.email


def clear_authenticated_session(request: Request) -> None:
    request.session.clear()


def get_authenticated_user(request: Request, session: Session) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return get_user_by_id(session, int(user_id))


def require_authenticated_user(request: Request, session: Session) -> User:
    user = get_authenticated_user(request, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user
