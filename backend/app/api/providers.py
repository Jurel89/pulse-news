from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.auth import require_authenticated_user
from app.deps import DbSession
from app.models import ApiKey, AuditEvent, Provider
from app.schemas import (
    ProviderCreateRequest,
    ProviderDetail,
    ProviderModelsResponse,
    ProviderSummary,
    ProviderTestResponse,
    ProviderUpdateRequest,
)

providers_router = APIRouter(prefix="/providers", tags=["providers"])

PROVIDER_MODEL_CATALOG = {
    "openai": ["gpt-4o-mini", "gpt-4o", "o4-mini"],
    "anthropic": ["claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "google": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "openrouter": [
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-2.0-flash-001",
    ],
}


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


def get_provider_or_404(db: DbSession, provider_id: int) -> Provider:
    provider = db.scalar(select(Provider).where(Provider.id == provider_id))
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found.")
    return provider


def serialize_provider_detail(provider: Provider) -> ProviderDetail:
    return ProviderDetail(
        **ProviderSummary.model_validate(provider).model_dump(),
        configuration=provider.configuration,
    )


def get_provider_models(provider: Provider) -> list[str]:
    models = list(PROVIDER_MODEL_CATALOG.get(provider.provider_type, []))
    if provider.default_model and provider.default_model not in models:
        models.insert(0, provider.default_model)
    return models


@providers_router.get("", response_model=list[ProviderSummary])
def list_providers(request: Request, db: DbSession) -> list[ProviderSummary]:
    require_authenticated_user(request, db)
    providers = db.scalars(select(Provider).order_by(Provider.updated_at.desc())).all()
    return [ProviderSummary.model_validate(provider) for provider in providers]


@providers_router.post("", response_model=ProviderDetail, status_code=status.HTTP_201_CREATED)
def create_provider(
    payload: ProviderCreateRequest,
    request: Request,
    db: DbSession,
) -> ProviderDetail:
    user = require_authenticated_user(request, db)
    provider = Provider(
        name=payload.name,
        provider_type=payload.provider_type,
        is_enabled=payload.is_enabled,
        description=payload.description,
        default_model=payload.default_model,
        configuration=payload.configuration,
    )
    db.add(provider)
    db.flush()
    create_audit_event(
        db,
        actor_email=user.email,
        action="provider.created",
        entity_type="provider",
        entity_id=str(provider.id),
        summary=f"Created provider {provider.name}",
        payload={"provider_type": provider.provider_type, "is_enabled": provider.is_enabled},
    )
    db.commit()
    db.refresh(provider)
    return serialize_provider_detail(provider)


@providers_router.get("/{provider_id}", response_model=ProviderDetail)
def get_provider(provider_id: int, request: Request, db: DbSession) -> ProviderDetail:
    require_authenticated_user(request, db)
    provider = get_provider_or_404(db, provider_id)
    return serialize_provider_detail(provider)


@providers_router.put("/{provider_id}", response_model=ProviderDetail)
def update_provider(
    provider_id: int,
    payload: ProviderUpdateRequest,
    request: Request,
    db: DbSession,
) -> ProviderDetail:
    user = require_authenticated_user(request, db)
    provider = get_provider_or_404(db, provider_id)

    provider.name = payload.name
    provider.provider_type = payload.provider_type
    provider.is_enabled = payload.is_enabled
    provider.description = payload.description
    provider.default_model = payload.default_model
    provider.configuration = payload.configuration

    db.add(provider)
    create_audit_event(
        db,
        actor_email=user.email,
        action="provider.updated",
        entity_type="provider",
        entity_id=str(provider.id),
        summary=f"Updated provider {provider.name}",
        payload={"provider_type": provider.provider_type, "is_enabled": provider.is_enabled},
    )
    db.commit()
    db.refresh(provider)
    return serialize_provider_detail(provider)


@providers_router.delete(
    "/{provider_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_provider(provider_id: int, request: Request, db: DbSession) -> Response:
    user = require_authenticated_user(request, db)
    provider = get_provider_or_404(db, provider_id)

    for newsletter in provider.newsletters:
        newsletter.provider_id = None

    create_audit_event(
        db,
        actor_email=user.email,
        action="provider.deleted",
        entity_type="provider",
        entity_id=str(provider.id),
        summary=f"Deleted provider {provider.name}",
        payload={"provider_type": provider.provider_type},
    )
    db.delete(provider)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@providers_router.get("/{provider_id}/models", response_model=ProviderModelsResponse)
def list_provider_models(
    provider_id: int,
    request: Request,
    db: DbSession,
) -> ProviderModelsResponse:
    require_authenticated_user(request, db)
    provider = get_provider_or_404(db, provider_id)
    return ProviderModelsResponse(
        models=get_provider_models(provider),
        default_model=provider.default_model,
    )


@providers_router.post("/{provider_id}/test", response_model=ProviderTestResponse)
def test_provider(provider_id: int, request: Request, db: DbSession) -> ProviderTestResponse:
    require_authenticated_user(request, db)
    provider = get_provider_or_404(db, provider_id)
    has_active_api_key = (
        db.scalar(
            select(ApiKey).where(
                ApiKey.provider_type == provider.provider_type,
                ApiKey.is_active.is_(True),
            )
        )
        is not None
    )

    if not provider.is_enabled:
        return ProviderTestResponse(
            status="warning",
            message="Provider is disabled. Enable it before using it for generation.",
            provider_type=provider.provider_type,
            default_model=provider.default_model,
            has_active_api_key=has_active_api_key,
        )

    if not has_active_api_key:
        return ProviderTestResponse(
            status="warning",
            message="Provider is enabled but has no active API key configured.",
            provider_type=provider.provider_type,
            default_model=provider.default_model,
            has_active_api_key=False,
        )

    return ProviderTestResponse(
        status="ok",
        message="Provider is enabled and has at least one active API key configured.",
        provider_type=provider.provider_type,
        default_model=provider.default_model,
        has_active_api_key=True,
    )
