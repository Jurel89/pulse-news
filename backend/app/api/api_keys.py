from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.auth import require_authenticated_user
from app.config import get_settings
from app.crypto import decrypt_secret, encrypt_secret
from app.deps import DbSession
from app.models import ApiKey, AuditEvent, Provider
from app.schemas import (
    ApiKeyCreateRequest,
    ApiKeyDetail,
    ApiKeySummary,
    ApiKeyTestResponse,
    ApiKeyUpdateRequest,
)

api_keys_router = APIRouter(prefix="/api-keys", tags=["api-keys"])
logger = logging.getLogger(__name__)


def create_audit_event(
    db: DbSession,
    *,
    actor_email: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    payload: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor_email=actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            payload_json=json.dumps(payload) if payload else None,
        )
    )


def get_api_key_or_404(db: DbSession, api_key_id: int) -> ApiKey:
    api_key = db.scalar(select(ApiKey).where(ApiKey.id == api_key_id))
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")
    return api_key


def mask_api_key(key_value: str) -> str:
    suffix = key_value[-4:] if key_value else ""
    return f"****{suffix}" if suffix else "****"


def serialize_api_key_detail(api_key: ApiKey) -> ApiKeyDetail:
    auth_type = getattr(api_key, "auth_type", "api_key") or "api_key"

    if auth_type == "oauth":
        plan = api_key.oauth_plan_type or "Connected"
        masked = f"ChatGPT ({plan})"
    else:
        try:
            decrypted_key_value = decrypt_secret(api_key.key_value)
        except Exception:
            decrypted_key_value = None
        masked = mask_api_key(decrypted_key_value) if decrypted_key_value else "****"

    return ApiKeyDetail(
        id=api_key.id,
        name=api_key.name,
        provider_type=api_key.provider_type,
        masked_key=masked,
        from_email=api_key.from_email,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
        auth_type=auth_type,
        oauth_plan_type=getattr(api_key, "oauth_plan_type", None),
        oauth_account_id=getattr(api_key, "oauth_account_id", None),
        oauth_expires_at=getattr(api_key, "oauth_expires_at", None),
    )


def _count_active_keys_for_provider(db: DbSession, provider_type: str) -> int:
    from sqlalchemy import func

    return (
        db.scalar(
            select(func.count(ApiKey.id)).where(
                ApiKey.provider_type == provider_type,
                ApiKey.is_active.is_(True),
            )
        )
        or 0
    )


def _has_enabled_providers_for_type(db: DbSession, provider_type: str) -> bool:
    return (
        db.scalar(
            select(Provider).where(
                Provider.provider_type == provider_type,
                Provider.is_enabled.is_(True),
            )
        )
        is not None
    )


@api_keys_router.get("", response_model=list[ApiKeySummary])
def list_api_keys(request: Request, db: DbSession) -> list[ApiKeySummary]:
    require_authenticated_user(request, db)
    api_keys = db.scalars(select(ApiKey).order_by(ApiKey.updated_at.desc())).all()
    return [serialize_api_key_detail(api_key) for api_key in api_keys]


@api_keys_router.post("", response_model=ApiKeyDetail, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreateRequest,
    request: Request,
    db: DbSession,
) -> ApiKeyDetail:
    user = require_authenticated_user(request, db)
    api_key = ApiKey(
        name=payload.name,
        provider_type=payload.provider_type,
        key_value=encrypt_secret(payload.key_value),
        from_email=payload.from_email,
        is_active=payload.is_active,
    )
    db.add(api_key)
    db.flush()
    create_audit_event(
        db,
        actor_email=user.email,
        action="api_key.created",
        entity_type="api_key",
        entity_id=str(api_key.id),
        summary=f"Created API key {api_key.name}",
        payload={"provider_type": api_key.provider_type, "is_active": api_key.is_active},
    )
    db.commit()
    db.refresh(api_key)
    return serialize_api_key_detail(api_key)


@api_keys_router.get("/{api_key_id}", response_model=ApiKeyDetail)
def get_api_key(api_key_id: int, request: Request, db: DbSession) -> ApiKeyDetail:
    require_authenticated_user(request, db)
    api_key = get_api_key_or_404(db, api_key_id)
    return serialize_api_key_detail(api_key)


@api_keys_router.put("/{api_key_id}", response_model=ApiKeyDetail)
def update_api_key(
    api_key_id: int,
    payload: ApiKeyUpdateRequest,
    request: Request,
    db: DbSession,
) -> ApiKeyDetail:
    user = require_authenticated_user(request, db)
    api_key = get_api_key_or_404(db, api_key_id)

    original_provider_type = api_key.provider_type
    original_is_active = api_key.is_active

    if payload.is_active is False and original_is_active is True:
        active_count = _count_active_keys_for_provider(db, original_provider_type)
        if active_count <= 1 and _has_enabled_providers_for_type(db, original_provider_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot deactivate the last active API key for "
                    f"'{original_provider_type}' while enabled providers exist. "
                    f"Create another API key first or disable the providers."
                ),
            )

    if payload.provider_type != original_provider_type and original_is_active:
        active_count = _count_active_keys_for_provider(db, original_provider_type)
        if active_count <= 1 and _has_enabled_providers_for_type(db, original_provider_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot reassign the last active API key from "
                    f"'{original_provider_type}' while enabled providers exist. "
                    f"Create another API key for '{original_provider_type}' first "
                    f"or disable those providers."
                ),
            )

    api_key.name = payload.name
    api_key.provider_type = payload.provider_type
    api_key.from_email = payload.from_email
    api_key.is_active = payload.is_active
    if payload.key_value is not None:
        api_key.key_value = encrypt_secret(payload.key_value)

    db.add(api_key)
    create_audit_event(
        db,
        actor_email=user.email,
        action="api_key.updated",
        entity_type="api_key",
        entity_id=str(api_key.id),
        summary=f"Updated API key {api_key.name}",
        payload={"provider_type": api_key.provider_type, "is_active": api_key.is_active},
    )
    db.commit()
    db.refresh(api_key)
    return serialize_api_key_detail(api_key)


@api_keys_router.delete(
    "/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_api_key(api_key_id: int, request: Request, db: DbSession) -> Response:
    user = require_authenticated_user(request, db)
    api_key = get_api_key_or_404(db, api_key_id)

    provider_type = api_key.provider_type
    is_active = api_key.is_active

    if is_active:
        active_count = _count_active_keys_for_provider(db, provider_type)
        if active_count <= 1 and _has_enabled_providers_for_type(db, provider_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot delete the last active API key for "
                    f"'{provider_type}' while enabled providers exist. "
                    f"Create another API key first or disable the providers."
                ),
            )

    for newsletter in api_key.newsletters:
        newsletter.api_key_id = None

    for newsletter in api_key.resend_newsletters:
        newsletter.resend_api_key_id = None

    create_audit_event(
        db,
        actor_email=user.email,
        action="api_key.deleted",
        entity_type="api_key",
        entity_id=str(api_key.id),
        summary=f"Deleted API key {api_key.name}",
        payload={"provider_type": api_key.provider_type},
    )
    db.delete(api_key)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_keys_router.post("/{api_key_id}/test", response_model=ApiKeyTestResponse)
def test_api_key(api_key_id: int, request: Request, db: DbSession) -> ApiKeyTestResponse:
    require_authenticated_user(request, db)
    api_key = get_api_key_or_404(db, api_key_id)

    if getattr(api_key, "auth_type", "api_key") == "oauth":
        has_token = api_key.oauth_access_token is not None
        return ApiKeyTestResponse(
            status="ok" if has_token else "warning",
            message=(
                "OAuth ChatGPT connection is active."
                if has_token
                else "OAuth connection found but access token is missing. Re-connect."
            ),
            provider_type=api_key.provider_type,
            masked_key=f"ChatGPT ({api_key.oauth_plan_type or 'Connected'})",
        )

    try:
        decrypted_key_value = decrypt_secret(api_key.key_value).strip()
    except Exception as exc:
        logger.warning(
            "Failed to decrypt API key id=%s provider_type=%s during test: %s",
            api_key.id,
            api_key.provider_type,
            exc,
        )
        return ApiKeyTestResponse(
            status="error",
            message=(
                "API key could not be decrypted. Re-save this key and try again. "
                "If the problem continues, create a new key entry."
            ),
            provider_type=api_key.provider_type,
            masked_key="****",
        )

    has_enabled_provider = (
        db.scalar(
            select(Provider).where(
                Provider.provider_type == api_key.provider_type,
                Provider.is_enabled.is_(True),
            )
        )
        is not None
    )
    resend_from_email = api_key.from_email or get_settings().resend_from_email
    resend_sender = resend_from_email.strip() if resend_from_email else ""

    if not decrypted_key_value:
        return ApiKeyTestResponse(
            status="error",
            message="API key is empty after decryption. Re-save this key and try again.",
            provider_type=api_key.provider_type,
            masked_key="****",
        )

    if not api_key.is_active:
        return ApiKeyTestResponse(
            status="warning",
            message="API key is inactive. Activate it before using it for provider requests.",
            provider_type=api_key.provider_type,
            masked_key=mask_api_key(decrypted_key_value),
        )

    if not has_enabled_provider and api_key.provider_type != "resend":
        return ApiKeyTestResponse(
            status="warning",
            message="API key is active, but there is no enabled provider configured for this type.",
            provider_type=api_key.provider_type,
            masked_key=mask_api_key(decrypted_key_value),
        )

    if api_key.provider_type == "resend":
        if not resend_sender:
            return ApiKeyTestResponse(
                status="warning",
                message=(
                    "Resend API key is active, but no sender email is configured. "
                    "Add a Sender Email to this API key or set PULSE_NEWS_RESEND_FROM_EMAIL. "
                    "Newsletter sends fail closed without a sender email."
                ),
                provider_type=api_key.provider_type,
                masked_key=mask_api_key(decrypted_key_value),
            )
        return ApiKeyTestResponse(
            status="ok",
            message=(
                f"Resend API key is active with sender '{resend_sender}'. "
                "Ready to send newsletter emails."
            ),
            provider_type=api_key.provider_type,
            masked_key=mask_api_key(decrypted_key_value),
        )

    return ApiKeyTestResponse(
        status="ok",
        message="API key is active and matches an enabled provider configuration.",
        provider_type=api_key.provider_type,
        masked_key=mask_api_key(decrypted_key_value),
    )
