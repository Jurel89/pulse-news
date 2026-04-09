from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_operator_count(session: Session) -> int:
    return session.scalar(select(func.count(User.id))) or 0


def bootstrap_enabled(session: Session) -> bool:
    return get_operator_count(session) == 0


def get_user_by_email(session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == normalize_email(email))
    return session.scalar(statement)


def get_user_by_id(session: Session, user_id: int) -> User | None:
    statement = select(User).where(User.id == user_id)
    return session.scalar(statement)
