"""OAuth routes for ChatGPT device-code and token lifecycle management.

All write endpoints emit AuditEvent rows, mirroring the api_keys.py pattern.
The in-memory ``_pending_device_auth`` dict keyed by device_auth_id holds
transient device-code sessions; it does not need to survive restarts because
device codes expire in ~15 minutes.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.api_keys import create_audit_event, get_api_key_or_404
from app.auth import require_authenticated_user
from app.crypto import decrypt_secret, encrypt_secret
from app.deps import DbSession
from app.models import ApiKey
from app.oauth.openai_chatgpt import (
    DeviceCodeInit,
    OpenAIOAuthError,
    TokenBundle,
    device_code_poll,
    device_code_start,
)
from app.oauth.openai_chatgpt import (
    refresh as oauth_refresh,
)

logger = logging.getLogger(__name__)

oauth_openai_router = APIRouter(prefix="/oauth/openai", tags=["oauth-openai"])

# In-memory map of device_auth_id → {device_auth_id, user_code, interval, expires_in, uri}
_pending_device_auth: dict[str, dict[str, Any]] = {}

_OAUTH_SENTINEL = "oauth:v1"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DeviceStartResponse(BaseModel):
    device_auth_id: str
    user_code: str
    verification_uri: str
    interval: int
    expires_in: int


class DevicePollRequest(BaseModel):
    device_auth_id: str


class DevicePollResponse(BaseModel):
    status: str  # "pending" | "complete"
    api_key_id: int | None = None


class OAuthStatusResponse(BaseModel):
    is_connected: bool
    plan_type: str | None = None
    account_id: str | None = None
    expires_at: datetime | None = None
    expires_in_seconds: int | None = None


class OAuthRefreshResponse(BaseModel):
    expires_at: datetime
    expires_in_seconds: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _materialize_oauth_connection(db: DbSession, bundle: TokenBundle) -> ApiKey:
    """Create or update the OAuth ApiKey row for the connected ChatGPT account.

    Single-operator assumption: there is at most one ``openai_chatgpt`` OAuth
    row per installation. If one already exists, update it; otherwise create.
    """
    existing = db.scalar(
        select(ApiKey).where(
            ApiKey.provider_type == "openai_chatgpt",
            ApiKey.auth_type == "oauth",
        )
    )

    plan_label = bundle.plan_type or "Connected"
    account_suffix = (bundle.account_id or "")[-8:] if bundle.account_id else ""
    name = f"ChatGPT ({plan_label})" + (f" …{account_suffix}" if account_suffix else "")

    if existing is not None:
        existing.name = name
        existing.key_value = encrypt_secret(_OAUTH_SENTINEL)
        existing.oauth_access_token = encrypt_secret(bundle.access_token)
        existing.oauth_refresh_token = encrypt_secret(bundle.refresh_token)
        existing.oauth_expires_at = bundle.expires_at
        existing.oauth_account_id = bundle.account_id
        existing.oauth_plan_type = bundle.plan_type
        existing.is_active = True
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    api_key = ApiKey(
        name=name,
        provider_type="openai_chatgpt",
        auth_type="oauth",
        key_value=encrypt_secret(_OAUTH_SENTINEL),
        oauth_access_token=encrypt_secret(bundle.access_token),
        oauth_refresh_token=encrypt_secret(bundle.refresh_token),
        oauth_expires_at=bundle.expires_at,
        oauth_account_id=bundle.account_id,
        oauth_plan_type=bundle.plan_type,
        is_active=True,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@oauth_openai_router.post(
    "/device/start",
    response_model=DeviceStartResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_device_code(request: Request, db: DbSession) -> DeviceStartResponse:
    user = require_authenticated_user(request, db)
    try:
        init: DeviceCodeInit = device_code_start()
    except OpenAIOAuthError as exc:
        logger.warning("Device-code start failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not start OpenAI device-code flow: {exc}",
        ) from exc

    _pending_device_auth[init.device_auth_id] = {
        "device_auth_id": init.device_auth_id,
        "user_code": init.user_code,
    }

    create_audit_event(
        db,
        actor_email=user.email,
        action="oauth_openai.device_start",
        entity_type="oauth_openai",
        entity_id=init.device_auth_id,
        summary="Started OpenAI ChatGPT device-code flow",
    )
    db.commit()

    return DeviceStartResponse(
        device_auth_id=init.device_auth_id,
        user_code=init.user_code,
        verification_uri=init.verification_uri,
        interval=init.interval,
        expires_in=init.expires_in,
    )


@oauth_openai_router.post("/device/poll", response_model=DevicePollResponse)
def poll_device_code(
    payload: DevicePollRequest,
    request: Request,
    db: DbSession,
) -> DevicePollResponse:
    user = require_authenticated_user(request, db)

    pending = _pending_device_auth.get(payload.device_auth_id)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown device_auth_id — start a new device flow.",
        )

    user_code = pending["user_code"]

    try:
        bundle: TokenBundle | None = device_code_poll(payload.device_auth_id, user_code)
    except OpenAIOAuthError as exc:
        logger.warning("Device-code poll error for %s: %s", payload.device_auth_id, exc)
        _pending_device_auth.pop(payload.device_auth_id, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device-code authorization failed: {exc}",
        ) from exc

    if bundle is None:
        return DevicePollResponse(status="pending")

    _pending_device_auth.pop(payload.device_auth_id, None)
    api_key = _materialize_oauth_connection(db, bundle)

    create_audit_event(
        db,
        actor_email=user.email,
        action="oauth_openai.connected",
        entity_type="api_key",
        entity_id=str(api_key.id),
        summary=f"Connected ChatGPT OAuth account (plan={bundle.plan_type})",
        payload={
            "account_id": bundle.account_id,
            "plan_type": bundle.plan_type,
        },
    )
    db.commit()

    return DevicePollResponse(status="complete", api_key_id=api_key.id)


@oauth_openai_router.post("/refresh/{api_key_id}", response_model=OAuthRefreshResponse)
def refresh_oauth_token(
    api_key_id: int,
    request: Request,
    db: DbSession,
) -> OAuthRefreshResponse:
    user = require_authenticated_user(request, db)
    api_key = get_api_key_or_404(db, api_key_id)

    if getattr(api_key, "auth_type", "api_key") != "oauth":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This API key is not an OAuth connection.",
        )

    try:
        raw_refresh = decrypt_secret(api_key.oauth_refresh_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not decrypt refresh token. Re-connect the ChatGPT account.",
        ) from exc

    try:
        bundle = oauth_refresh(raw_refresh)
    except OpenAIOAuthError as exc:
        logger.warning("OAuth refresh failed for api_key id=%s: %s", api_key_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Token refresh failed: {exc}",
        ) from exc

    api_key.oauth_access_token = encrypt_secret(bundle.access_token)
    api_key.oauth_refresh_token = encrypt_secret(bundle.refresh_token)
    api_key.oauth_expires_at = bundle.expires_at
    if bundle.account_id:
        api_key.oauth_account_id = bundle.account_id
    if bundle.plan_type:
        api_key.oauth_plan_type = bundle.plan_type
    db.add(api_key)

    create_audit_event(
        db,
        actor_email=user.email,
        action="oauth_openai.refreshed",
        entity_type="api_key",
        entity_id=str(api_key.id),
        summary=f"Refreshed ChatGPT OAuth token (expires={bundle.expires_at})",
    )
    db.commit()

    now = datetime.now(UTC)
    expires_in_seconds = max(0, int((bundle.expires_at - now).total_seconds()))
    return OAuthRefreshResponse(
        expires_at=bundle.expires_at,
        expires_in_seconds=expires_in_seconds,
    )


@oauth_openai_router.get("/{api_key_id}/status", response_model=OAuthStatusResponse)
def get_oauth_status(
    api_key_id: int,
    request: Request,
    db: DbSession,
) -> OAuthStatusResponse:
    require_authenticated_user(request, db)
    api_key = get_api_key_or_404(db, api_key_id)

    if getattr(api_key, "auth_type", "api_key") != "oauth":
        return OAuthStatusResponse(is_connected=False)

    now = datetime.now(UTC)
    expires_at = api_key.oauth_expires_at
    expires_in_seconds: int | None = None
    if expires_at is not None:
        # SQLite returns naive datetimes; treat them as UTC.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        delta = (expires_at - now).total_seconds()
        expires_in_seconds = max(0, int(delta))

    return OAuthStatusResponse(
        is_connected=api_key.is_active,
        plan_type=api_key.oauth_plan_type,
        account_id=api_key.oauth_account_id,
        expires_at=expires_at,
        expires_in_seconds=expires_in_seconds,
    )


@oauth_openai_router.delete(
    "/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_oauth_connection(
    api_key_id: int,
    request: Request,
    db: DbSession,
) -> Response:
    user = require_authenticated_user(request, db)
    api_key = get_api_key_or_404(db, api_key_id)

    if getattr(api_key, "auth_type", "api_key") != "oauth":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This API key is not an OAuth connection.",
        )

    for newsletter in api_key.newsletters:
        newsletter.api_key_id = None
    for newsletter in api_key.resend_newsletters:
        newsletter.resend_api_key_id = None

    create_audit_event(
        db,
        actor_email=user.email,
        action="oauth_openai.deleted",
        entity_type="api_key",
        entity_id=str(api_key.id),
        summary=f"Deleted ChatGPT OAuth connection '{api_key.name}'",
        payload={"account_id": api_key.oauth_account_id},
    )
    db.delete(api_key)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
