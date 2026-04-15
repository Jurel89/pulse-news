from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.auth import (
    bootstrap_enabled,
    claim_bootstrap,
    clear_authenticated_session,
    get_authenticated_user,
    get_user_by_email,
    mark_bootstrap_complete,
    normalize_email,
    require_authenticated_user,
    set_authenticated_session,
)
from app.config import get_settings
from app.deps import DbSession
from app.models import User
from app.schemas import (
    AuthActionResponse,
    BootstrapRequest,
    ChangePasswordRequest,
    LoginRequest,
    SessionResponse,
    SystemSettingsResponse,
    UserSummary,
)
from app.security import hash_password, verify_password

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _system_settings_response(db: DbSession) -> SystemSettingsResponse:
    return SystemSettingsResponse(initialized=not bootstrap_enabled(db))


def _session_response(*, db: DbSession, user: User | None) -> SessionResponse:
    return SessionResponse(
        initialized=not bootstrap_enabled(db),
        authenticated=user is not None,
        user=UserSummary.model_validate(user) if user else None,
    )


@auth_router.get("/session", response_model=SessionResponse)
def session_status(request: Request, db: DbSession) -> SessionResponse:
    user = get_authenticated_user(request, db)
    return _session_response(db=db, user=user)


@auth_router.post("/bootstrap", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_operator(
    payload: BootstrapRequest,
    request: Request,
    db: DbSession,
) -> SessionResponse:
    settings = get_settings()
    if settings.environment == "production":
        if not settings.bootstrap_secret:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Bootstrap is disabled. "
                    "Set PULSE_NEWS_BOOTSTRAP_SECRET to enable initial setup."
                ),
            )
        if payload.bootstrap_secret != settings.bootstrap_secret:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid bootstrap secret.",
            )

    if not bootstrap_enabled(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Operator account already exists.",
        )

    claim_bootstrap(db)

    email = normalize_email(payload.email)
    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()

    mark_bootstrap_complete(db, user.id)
    db.commit()
    db.refresh(user)

    set_authenticated_session(request, user.id, user.email)
    return _session_response(db=db, user=user)


@auth_router.post("/login", response_model=SessionResponse)
def login_operator(payload: LoginRequest, request: Request, db: DbSession) -> SessionResponse:
    user = get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    set_authenticated_session(request, user.id, user.email)
    return _session_response(db=db, user=user)


@auth_router.post("/logout", response_model=AuthActionResponse)
def logout_operator(request: Request) -> AuthActionResponse:
    clear_authenticated_session(request)
    return AuthActionResponse(message="Logged out successfully.")


@auth_router.post("/change-password", response_model=AuthActionResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: DbSession,
) -> AuthActionResponse:
    user = require_authenticated_user(request, db)
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return AuthActionResponse(message="Password updated successfully.")
