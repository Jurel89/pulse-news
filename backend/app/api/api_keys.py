from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.auth import require_authenticated_user
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
    return ApiKeyDetail(
        id=api_key.id,
        name=api_key.name,
        provider_type=api_key.provider_type,
        masked_key=mask_api_key(api_key.key_value),
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
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
        key_value=payload.key_value,
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

    api_key.name = payload.name
    api_key.provider_type = payload.provider_type
    api_key.is_active = payload.is_active
    if payload.key_value is not None:
        api_key.key_value = payload.key_value

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
    has_enabled_provider = (
        db.scalar(
            select(Provider).where(
                Provider.provider_type == api_key.provider_type,
                Provider.is_enabled.is_(True),
            )
        )
        is not None
    )

    if not api_key.is_active:
        return ApiKeyTestResponse(
            status="warning",
            message="API key is inactive. Activate it before using it for provider requests.",
            provider_type=api_key.provider_type,
            masked_key=mask_api_key(api_key.key_value),
        )

    if not has_enabled_provider:
        return ApiKeyTestResponse(
            status="warning",
            message="API key is active, but there is no enabled provider configured for this type.",
            provider_type=api_key.provider_type,
            masked_key=mask_api_key(api_key.key_value),
        )

    return ApiKeyTestResponse(
        status="ok",
        message="API key is active and matches an enabled provider configuration.",
        provider_type=api_key.provider_type,
        masked_key=mask_api_key(api_key.key_value),
    )
