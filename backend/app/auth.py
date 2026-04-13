from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.models import OperationMode, SystemSettings, User, utc_now

SYSTEM_SETTINGS_ID = 1


@dataclass(frozen=True)
class OperationModeState:
    ai_generation_mode: str
    email_delivery_mode: str


def _normalize_operation_mode(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized == OperationMode.SIMULATED.value:
        return OperationMode.SIMULATED.value
    return OperationMode.LIVE.value


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


def get_operation_mode_state(session: Session) -> OperationModeState:
    settings = get_system_settings(session)
    return OperationModeState(
        ai_generation_mode=_normalize_operation_mode(
            settings.ai_generation_mode if settings is not None else None
        ),
        email_delivery_mode=_normalize_operation_mode(
            settings.email_delivery_mode if settings is not None else None
        ),
    )


def resolve_operation_mode_state(*, db_session: Session | None = None) -> OperationModeState:
    if db_session is not None:
        return get_operation_mode_state(db_session)

    from app.database import get_session_maker

    session = get_session_maker()()
    try:
        return get_operation_mode_state(session)
    finally:
        session.close()


def get_ai_generation_mode(*, db_session: Session | None = None) -> str:
    return resolve_operation_mode_state(db_session=db_session).ai_generation_mode


def get_email_delivery_mode(*, db_session: Session | None = None) -> str:
    return resolve_operation_mode_state(db_session=db_session).email_delivery_mode


def update_system_settings_operation_modes(
    session: Session,
    *,
    ai_generation_mode: str | None = None,
    email_delivery_mode: str | None = None,
) -> SystemSettings:
    settings = get_or_create_system_settings(session)
    if ai_generation_mode is not None:
        settings.ai_generation_mode = _normalize_operation_mode(ai_generation_mode)
    if email_delivery_mode is not None:
        settings.email_delivery_mode = _normalize_operation_mode(email_delivery_mode)
    session.add(settings)
    session.flush()
    return settings


def get_operator_count(session: Session) -> int:
    return session.scalar(select(func.count(User.id))) or 0


def bootstrap_enabled(session: Session) -> bool:
    settings = get_system_settings(session)
    if settings is not None and settings.initialized:
        return False
    return get_operator_count(session) == 0


def claim_bootstrap(session: Session) -> bool:
    """Atomically claim bootstrap. Returns True if this call won the race."""
    settings = get_system_settings(session)
    if settings is not None and settings.initialized:
        return False
    if get_operator_count(session) > 0:
        return False

    inserted = session.execute(
        insert(SystemSettings)
        .values(id=SYSTEM_SETTINGS_ID, initialized=True)
        .prefix_with("OR IGNORE")
    )
    if (inserted.rowcount or 0) == 1:
        return True

    claimed = session.execute(
        update(SystemSettings)
        .where(SystemSettings.id == SYSTEM_SETTINGS_ID, SystemSettings.initialized.is_(False))
        .values(initialized=True)
    )
    return (claimed.rowcount or 0) == 1


def mark_bootstrap_complete(session: Session, user_id: int) -> None:
    settings = get_or_create_system_settings(session)
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
