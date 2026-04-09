from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import bootstrap_enabled, get_user_by_email, get_user_by_id, normalize_email
from app.deps import DbSession
from app.models import User
from app.schemas import (
    AuthActionResponse,
    BootstrapRequest,
    ChangePasswordRequest,
    LoginRequest,
    SessionResponse,
    UserSummary,
)
from app.security import hash_password, verify_password


auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _set_authenticated_session(request: Request, user: User) -> None:
    request.session["user_id"] = user.id
    request.session["user_email"] = user.email


def _clear_authenticated_session(request: Request) -> None:
    request.session.clear()


def _get_authenticated_user(request: Request, session: Session) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return get_user_by_id(session, int(user_id))


def _require_authenticated_user(request: Request, session: Session) -> User:
    user = _get_authenticated_user(request, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


@auth_router.get("/session", response_model=SessionResponse)
def session_status(request: Request, db: DbSession) -> SessionResponse:
    user = _get_authenticated_user(request, db)
    return SessionResponse(
        initialized=not bootstrap_enabled(db),
        authenticated=user is not None,
        user=UserSummary.model_validate(user) if user else None,
    )


@auth_router.post("/bootstrap", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_operator(payload: BootstrapRequest, request: Request, db: DbSession) -> SessionResponse:
    if not bootstrap_enabled(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Operator account already exists.",
        )

    email = normalize_email(payload.email)
    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    _set_authenticated_session(request, user)
    return SessionResponse(initialized=True, authenticated=True, user=UserSummary.model_validate(user))


@auth_router.post("/login", response_model=SessionResponse)
def login_operator(payload: LoginRequest, request: Request, db: DbSession) -> SessionResponse:
    user = get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    _set_authenticated_session(request, user)
    return SessionResponse(initialized=True, authenticated=True, user=UserSummary.model_validate(user))


@auth_router.post("/logout", response_model=AuthActionResponse)
def logout_operator(request: Request) -> AuthActionResponse:
    _clear_authenticated_session(request)
    return AuthActionResponse(message="Logged out successfully.")


@auth_router.post("/change-password", response_model=AuthActionResponse)
def change_password(payload: ChangePasswordRequest, request: Request, db: DbSession) -> AuthActionResponse:
    user = _require_authenticated_user(request, db)
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return AuthActionResponse(message="Password updated successfully.")
