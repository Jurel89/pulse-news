from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.ai_generation import (
    discover_models_for_provider,
    resolve_provider_test_config,
    validate_provider_model,
)
from app.auth import require_authenticated_user
from app.deps import DbSession
from app.models import ApiKey, AuditEvent, Provider
from app.oauth.openai_chatgpt import CHATGPT_SUPPORTED_MODELS
from app.schemas import (
    ProviderCreateRequest,
    ProviderDetail,
    ProviderModelsResponse,
    ProviderSummary,
    ProviderTestResponse,
    ProviderUpdateRequest,
)

providers_router = APIRouter(prefix="/providers", tags=["providers"])

PROVIDER_MODEL_CATALOG: dict[str, list[str]] = {}

OPENAI_CHATGPT_RECOMMENDED_MODELS = list(CHATGPT_SUPPORTED_MODELS)


def _validate_chatgpt_model(model_name: str | None) -> None:
    if model_name and model_name not in CHATGPT_SUPPORTED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Model '{model_name}' is not supported for ChatGPT subscription. "
                f"Supported models: {', '.join(sorted(CHATGPT_SUPPORTED_MODELS))}."
            ),
        )


RECOMMENDED_MODELS: dict[str, list[str]] = {
    "openai": ["gpt-4o-mini", "gpt-4o", "o4-mini"],
    "anthropic": ["claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "google": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "openrouter": [
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-2.0-flash-001",
    ],
    "zai": ["glm-5.1", "glm-5-turbo"],
    "kimi": ["kimi-k2.5", "kimi-k2-turbo-preview"],
    "openai_chatgpt": OPENAI_CHATGPT_RECOMMENDED_MODELS,
}

PROVIDER_PRESETS = [
    {
        "key": "openai",
        "name": "OpenAI",
        "adapter": "openai",
        "base_url": "https://api.openai.com/v1",
        "recommended_models": ["gpt-4o-mini", "gpt-4o", "o4-mini"],
        "supports_discovery": True,
    },
    {
        "key": "anthropic",
        "name": "Anthropic",
        "adapter": "anthropic",
        "base_url": None,
        "recommended_models": ["claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest"],
        "supports_discovery": True,
    },
    {
        "key": "gemini",
        "name": "Google Gemini",
        "adapter": "gemini",
        "base_url": None,
        "recommended_models": ["gemini-2.5-flash", "gemini-2.5-pro"],
        "supports_discovery": True,
    },
    {
        "key": "openrouter",
        "name": "OpenRouter",
        "adapter": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "recommended_models": [
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-001",
        ],
        "supports_discovery": True,
    },
    {
        "key": "zai",
        "name": "Z.AI",
        "adapter": "openai_compatible",
        "base_url": "https://api.z.ai/api/paas/v4/",
        "recommended_models": ["glm-5.1", "glm-5-turbo"],
        "supports_discovery": True,
    },
    {
        "key": "kimi",
        "name": "Kimi",
        "adapter": "openai_compatible",
        "base_url": "https://api.kimi.com/coding/v1",
        "recommended_models": ["kimi-k2.5", "kimi-k2-turbo-preview"],
        "supports_discovery": True,
    },
    {
        "key": "openai_chatgpt",
        "name": "OpenAI ChatGPT (Subscription)",
        "adapter": "openai_chatgpt",
        "base_url": "https://chatgpt.com/backend-api",
        "recommended_models": OPENAI_CHATGPT_RECOMMENDED_MODELS,
        "supports_discovery": False,
        # Signals to the frontend that this provider uses OAuth rather than an API key.
        "auth_mode": "oauth",
    },
]


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


def _safe_decrypt(key_value: str) -> str | None:
    from app.crypto import decrypt_secret

    try:
        return decrypt_secret(key_value)
    except Exception:
        return None


def _uses_oauth_connection(provider_type: str) -> bool:
    return provider_type == "openai_chatgpt"


def _validate_chatgpt_oauth_token(api_key: ApiKey) -> bool:
    """Check that the stored OAuth token is usable.

    If the access token is expired but a refresh token exists, attempt a
    refresh — matching the runtime behavior that auto-refreshes before
    generation.  The refreshed tokens are persisted back to the ApiKey row.
    Only report failure if the token is truly unrecoverable.
    """
    from datetime import UTC
    from datetime import datetime as _dt

    from app.crypto import decrypt_secret, encrypt_secret
    from app.oauth import openai_chatgpt as _oauth

    try:
        access_token = decrypt_secret(api_key.oauth_access_token)
    except Exception:
        return False
    if not access_token:
        return False

    expires_at = api_key.oauth_expires_at
    is_expired = False
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        is_expired = _dt.now(UTC) >= expires_at

    if is_expired:
        try:
            raw_refresh = decrypt_secret(api_key.oauth_refresh_token)
            if raw_refresh:
                bundle = _oauth.refresh(raw_refresh)
                api_key.oauth_access_token = encrypt_secret(bundle.access_token)
                api_key.oauth_refresh_token = encrypt_secret(bundle.refresh_token)
                api_key.oauth_expires_at = bundle.expires_at
                return True
        except Exception:
            pass
        return False

    return True


def _missing_provider_credential_detail(provider_type: str) -> str:
    if _uses_oauth_connection(provider_type):
        return (
            f"No active OAuth connection found for provider type '{provider_type}'. "
            "Connect a ChatGPT account first."
        )
    return f"No active API key found for provider type '{provider_type}'. Create an API key first."


def get_provider_models(provider: Provider, *, db: DbSession | None = None) -> list[str]:
    api_key: str | None = None
    if db is not None and not _uses_oauth_connection(provider.provider_type):
        active_key = _get_active_api_key(db, provider.provider_type)
        if active_key:
            api_key = _safe_decrypt(active_key.key_value)
    discovered = discover_models_for_provider(
        provider.provider_type,
        api_key=api_key,
        configuration=provider.configuration,
    )
    recommended = RECOMMENDED_MODELS.get(provider.provider_type, [])
    seen: set[str] = set()
    models: list[str] = []
    for m in recommended:
        if m not in seen:
            seen.add(m)
            models.append(m)
    for m in discovered:
        if m not in seen:
            seen.add(m)
            models.append(m)
    if provider.default_model and provider.default_model not in seen:
        models.insert(0, provider.default_model)
    return models


@providers_router.get("", response_model=list[ProviderSummary])
def list_providers(request: Request, db: DbSession) -> list[ProviderSummary]:
    require_authenticated_user(request, db)
    providers = db.scalars(select(Provider).order_by(Provider.updated_at.desc())).all()
    return [ProviderSummary.model_validate(provider) for provider in providers]


def _get_active_api_key(db: DbSession, provider_type: str) -> ApiKey | None:
    query = (
        select(ApiKey)
        .where(
            ApiKey.provider_type == provider_type,
            ApiKey.is_active.is_(True),
        )
        .order_by(ApiKey.updated_at.desc(), ApiKey.id.desc())
    )
    # For the OAuth provider, only OAuth rows are valid credentials.
    if provider_type == "openai_chatgpt":
        query = query.where(ApiKey.auth_type == "oauth")
    return db.scalar(query)


@providers_router.post("", response_model=ProviderDetail, status_code=status.HTTP_201_CREATED)
def create_provider(
    payload: ProviderCreateRequest,
    request: Request,
    db: DbSession,
) -> ProviderDetail:
    user = require_authenticated_user(request, db)

    active_key = _get_active_api_key(db, payload.provider_type)
    if active_key is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_missing_provider_credential_detail(payload.provider_type),
        )

    if payload.provider_type == "openai_chatgpt":
        _validate_chatgpt_model(payload.default_model)

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


@providers_router.get("/presets/list")
def list_provider_presets(request: Request, db: DbSession) -> list[dict]:
    require_authenticated_user(request, db)
    return PROVIDER_PRESETS


@providers_router.get("/presets/{provider_type}/models")
def list_preset_models(
    provider_type: str, request: Request, db: DbSession
) -> ProviderModelsResponse:
    require_authenticated_user(request, db)
    active_key = _get_active_api_key(db, provider_type)
    api_key: str | None = None
    if active_key and not _uses_oauth_connection(provider_type):
        api_key = _safe_decrypt(active_key.key_value)
    models = discover_models_for_provider(provider_type, api_key=api_key)
    recommended = RECOMMENDED_MODELS.get(provider_type, [])
    seen: set[str] = set()
    merged: list[str] = []
    for m in recommended:
        if m not in seen:
            seen.add(m)
            merged.append(m)
    for m in models:
        if m not in seen:
            seen.add(m)
            merged.append(m)

    verified_model: str | None = None
    verification_message: str | None = None
    model_to_verify = recommended[0] if recommended else None
    if model_to_verify and not _uses_oauth_connection(provider_type):
        active_key = _get_active_api_key(db, provider_type)
        if active_key:
            api_key = _safe_decrypt(active_key.key_value)
            if api_key:
                ok, msg = validate_provider_model(provider_type, model_to_verify, api_key)
                if ok:
                    verified_model = model_to_verify
                else:
                    verification_message = msg

    return ProviderModelsResponse(
        models=merged,
        default_model=recommended[0] if recommended else None,
        verified_model=verified_model,
        verification_message=verification_message,
    )


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

    effective_provider_type = payload.provider_type or provider.provider_type
    active_key = _get_active_api_key(db, effective_provider_type)
    if active_key is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_missing_provider_credential_detail(effective_provider_type),
        )

    if effective_provider_type == "openai_chatgpt":
        _validate_chatgpt_model(
            payload.default_model if payload.default_model is not None else provider.default_model
        )

    provider.name = payload.name or provider.name
    provider.provider_type = effective_provider_type
    provider.is_enabled = payload.is_enabled
    provider.description = (
        payload.description if payload.description is not None else provider.description
    )
    provider.default_model = (
        payload.default_model if payload.default_model is not None else provider.default_model
    )
    provider.configuration = (
        payload.configuration if payload.configuration is not None else provider.configuration
    )

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

    models = get_provider_models(provider, db=db)
    verified_model: str | None = None
    verification_message: str | None = None

    model_to_verify = (
        provider.default_model or (RECOMMENDED_MODELS.get(provider.provider_type, [None])[0])
    )
    if model_to_verify and not _uses_oauth_connection(provider.provider_type):
        active_key = _get_active_api_key(db, provider.provider_type)
        if active_key:
            api_key = _safe_decrypt(active_key.key_value)
            if api_key:
                ok, msg = validate_provider_model(
                    provider.provider_type,
                    model_to_verify,
                    api_key,
                    configuration=provider.configuration,
                )
                if ok:
                    verified_model = model_to_verify
                else:
                    verification_message = msg

    return ProviderModelsResponse(
        models=models,
        default_model=provider.default_model,
        verified_model=verified_model,
        verification_message=verification_message,
    )


@providers_router.post("/{provider_id}/test", response_model=ProviderTestResponse)
def test_provider(provider_id: int, request: Request, db: DbSession) -> ProviderTestResponse:
    require_authenticated_user(request, db)
    provider = get_provider_or_404(db, provider_id)

    active_key = _get_active_api_key(db, provider.provider_type)
    has_active_api_key = active_key is not None

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
            message=(
                "Provider is enabled but has no active OAuth connection configured."
                if provider.provider_type == "openai_chatgpt"
                else "Provider is enabled but has no active API key configured."
            ),
            provider_type=provider.provider_type,
            default_model=provider.default_model,
            has_active_api_key=False,
        )

    # openai_chatgpt uses OAuth — validate token health instead of a LiteLLM ping.
    if provider.provider_type == "openai_chatgpt":
        oauth_active = (
            active_key is not None and getattr(active_key, "auth_type", "api_key") == "oauth"
        )
        if not oauth_active:
            return ProviderTestResponse(
                status="warning",
                message="ChatGPT OAuth connection required.",
                provider_type=provider.provider_type,
                default_model=provider.default_model,
                has_active_api_key=False,
            )
        token_ok = _validate_chatgpt_oauth_token(active_key)
        return ProviderTestResponse(
            status="ok" if token_ok else "warning",
            message=(
                "ChatGPT OAuth connection is healthy."
                if token_ok
                else "ChatGPT OAuth token is expired or invalid. Re-connect."
            ),
            provider_type=provider.provider_type,
            default_model=provider.default_model,
            has_active_api_key=has_active_api_key,
        )

    try:
        from litellm import completion
    except Exception:
        return ProviderTestResponse(
            status="ok",
            message=(
                "Provider is enabled and has an active API key. "
                "(LiteLLM not installed — live test skipped.)"
            ),
            provider_type=provider.provider_type,
            default_model=provider.default_model,
            has_active_api_key=True,
        )

    model_name = (
        provider.default_model or RECOMMENDED_MODELS.get(provider.provider_type, ["test"])[0]
    )

    try:
        full_model, completion_kwargs = resolve_provider_test_config(
            provider, model_name=model_name
        )
    except (ValueError, json.JSONDecodeError) as exc:
        return ProviderTestResponse(
            status="warning",
            message=f"Invalid provider configuration: {exc}",
            provider_type=provider.provider_type,
            default_model=provider.default_model,
            has_active_api_key=True,
        )

    decrypted_key = _safe_decrypt(active_key.key_value)
    if not decrypted_key:
        return ProviderTestResponse(
            status="warning",
            message="Active API key could not be decrypted. Re-save the key and try again.",
            provider_type=provider.provider_type,
            default_model=provider.default_model,
            has_active_api_key=True,
        )

    try:
        completion(
            model=full_model,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            api_key=decrypted_key,
            max_tokens=3,
            **completion_kwargs,
        )
    except Exception as exc:
        return ProviderTestResponse(
            status="warning",
            message=f"API key found but live test failed: {type(exc).__name__}",
            provider_type=provider.provider_type,
            default_model=provider.default_model,
            has_active_api_key=True,
        )

    from app.models import utc_now

    active_key.last_used_at = utc_now()
    db.commit()

    return ProviderTestResponse(
        status="ok",
        message=f"Connection successful. Verified API key with live call to {full_model}.",
        provider_type=provider.provider_type,
        default_model=provider.default_model,
        has_active_api_key=True,
    )
