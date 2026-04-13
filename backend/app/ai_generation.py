from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from app.crypto import decrypt_secret
from app.models import Newsletter

try:  # pragma: no cover - exercised conditionally when dependency is present and configured
    from litellm import completion
except Exception:  # pragma: no cover - local fallback path handles absence
    completion = None


@dataclass
class GeneratedDraft:
    status: str
    mode: str
    message: str
    subject: str
    preheader: str
    body_text: str


SUPPORTED_PROVIDERS = {"anthropic", "gemini", "google", "openai", "openrouter", "zai", "kimi"}

# Maps our internal provider_type names to the LiteLLM provider prefix.
# Providers not listed here use their own name as the prefix.
PROVIDER_TO_LITELLM_PREFIX: dict[str, str] = {
    "kimi": "moonshot",
    "google": "gemini",
}

PRESET_BASE_URLS: dict[str, str] = {
    "zai": "https://api.z.ai/api/paas/v4/",
    "kimi": "https://api.kimi.com/coding/v1",
}


def _get_newsletter_provider(newsletter: Newsletter):
    from sqlalchemy import select

    from app.database import get_session_maker
    from app.models import Provider

    if newsletter.provider is not None:
        return newsletter.provider
    if newsletter.provider_id is None:
        return None

    session = get_session_maker()()
    try:
        return session.scalar(select(Provider).where(Provider.id == newsletter.provider_id))
    finally:
        session.close()


def _normalized_provider_name(newsletter: Newsletter) -> str:
    provider = _get_newsletter_provider(newsletter)
    source = provider.provider_type if provider is not None else newsletter.provider_name
    return source.strip().lower()


def _resolved_model_name(newsletter: Newsletter) -> str:
    configured_model = newsletter.model_name.strip()
    if configured_model:
        return configured_model

    provider = _get_newsletter_provider(newsletter)
    if provider is not None and provider.default_model:
        return provider.default_model.strip()

    return ""


def _provider_model_name(newsletter: Newsletter) -> str:
    provider_name = _normalized_provider_name(newsletter)
    model_name = _resolved_model_name(newsletter)
    return _resolve_full_model_name(provider_name, model_name)


def _get_api_key_for_newsletter(newsletter: Newsletter) -> str | None:
    from sqlalchemy import select

    from app.database import get_session_maker
    from app.models import ApiKey

    provider_name = _normalized_provider_name(newsletter)
    session = get_session_maker()()

    try:
        if newsletter.api_key_id:
            api_key = session.scalar(
                select(ApiKey).where(
                    ApiKey.id == newsletter.api_key_id,
                    ApiKey.is_active.is_(True),
                    ApiKey.provider_type == provider_name,
                )
            )
            if api_key and api_key.key_value:
                try:
                    return decrypt_secret(api_key.key_value)
                except Exception:
                    pass

        active_provider_key = session.scalar(
            select(ApiKey)
            .where(
                ApiKey.provider_type == provider_name,
                ApiKey.is_active.is_(True),
            )
            .order_by(ApiKey.updated_at.desc(), ApiKey.id.desc())
        )
        if active_provider_key and active_provider_key.key_value:
            try:
                return decrypt_secret(active_provider_key.key_value)
            except Exception:
                pass
    finally:
        session.close()

    env_by_provider = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "google": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "zai": "ZAI_API_KEY",
        "kimi": "KIMI_API_KEY",
    }
    env_name = env_by_provider.get(provider_name)
    if env_name:
        value = os.getenv(env_name)
        if value:
            return value
    # LiteLLM uses MOONSHOT_API_KEY for the moonshot provider
    if provider_name == "kimi":
        return os.getenv("MOONSHOT_API_KEY")
    return None


def _has_live_provider_credentials(newsletter: Newsletter) -> bool:
    return _get_api_key_for_newsletter(newsletter) is not None


def _provider_completion_configuration(newsletter: Newsletter) -> dict[str, Any]:
    provider = _get_newsletter_provider(newsletter)
    provider_name = _normalized_provider_name(newsletter)
    model_name = _resolved_model_name(newsletter)

    if provider is not None:
        _, config = resolve_provider_test_config(provider, model_name=model_name)
        return config

    return _config_from_provider_type(provider_name, configuration=None)


def _fallback_generate(newsletter: Newsletter) -> GeneratedDraft:
    subject = newsletter.draft_subject.strip() or f"{newsletter.name}: generated draft"
    preheader = (
        newsletter.draft_preheader
        or newsletter.description
        or "Generated locally because no live provider credentials are configured."
    ).strip()
    body_text = newsletter.draft_body_text.strip() or (
        "Fallback draft outline:\n"
        "- Lead with the newsletter angle and core update.\n"
        "- Highlight 3 concise points worth operator attention.\n"
        "- Close with a short next-step or takeaway."
    )
    return GeneratedDraft(
        status="fallback",
        mode="local-generator",
        message=(
            "Generated a local fallback draft because no live provider "
            "credentials were configured for this provider."
        ),
        subject=subject,
        preheader=preheader,
        body_text=body_text,
    )


def generate_newsletter_draft(newsletter: Newsletter) -> GeneratedDraft:
    provider_name = _normalized_provider_name(newsletter)

    # Enforce provider enabled at generation time
    provider = _get_newsletter_provider(newsletter)
    if provider is not None and not provider.is_enabled:
        return GeneratedDraft(
            status="error",
            mode="none",
            message=f"Provider '{provider.name}' is disabled. Enable it before generating.",
            subject=newsletter.draft_subject or newsletter.name,
            preheader=newsletter.draft_preheader or "",
            body_text=newsletter.draft_body_text or "",
        )

    if provider_name not in SUPPORTED_PROVIDERS:
        supported_providers = ", ".join(sorted(SUPPORTED_PROVIDERS))
        return GeneratedDraft(
            status="error",
            mode="none",
            message=(
                f"Unsupported provider: '{newsletter.provider_name}'. "
                f"Supported: {supported_providers}"
            ),
            subject=newsletter.draft_subject or newsletter.name,
            preheader=newsletter.draft_preheader or "",
            body_text=newsletter.draft_body_text or "",
        )

    if completion is None or not _has_live_provider_credentials(newsletter):
        return _fallback_generate(newsletter)

    prompt = "\n".join(
        [
            f"Newsletter name: {newsletter.name}",
            f"Description: {newsletter.description or 'None'}",
            f"Audience label: {newsletter.audience_name}",
            "Generate a concise newsletter draft with:",
            "1. A subject line",
            "2. A preheader",
            "3. A plain-text newsletter body with short sections",
            "",
            f"Prompt instructions:\n{newsletter.prompt}",
            "",
            "Return the result as plain text in this exact format:",
            "SUBJECT: ...",
            "PREHEADER: ...",
            "BODY:",
            "...",
        ]
    )

    try:
        api_key = _get_api_key_for_newsletter(newsletter)
        completion_kwargs = _provider_completion_configuration(newsletter)

        # Add User-Agent header for Kimi Code API compatibility
        if _normalized_provider_name(newsletter) == "kimi":
            completion_kwargs["extra_headers"] = {
                "User-Agent": os.environ.get("LITELLM_USER_AGENT", "claude-code/0.1.0")
            }

        response = completion(
            model=_provider_model_name(newsletter),
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
            **completion_kwargs,
        )
        content = response.choices[0].message.content or ""
    except ValueError as exc:
        return GeneratedDraft(
            status="error",
            mode="none",
            message=str(exc),
            subject=newsletter.draft_subject or newsletter.name,
            preheader=newsletter.draft_preheader or newsletter.description or "",
            body_text=newsletter.draft_body_text or "",
        )
    except Exception as exc:
        fallback = _fallback_generate(newsletter)
        fallback.message = f"Live generation failed, using local fallback instead: {exc}"
        return fallback

    lines = content.splitlines()
    subject = newsletter.name
    preheader = newsletter.description or ""
    body_lines: list[str] = []
    in_body = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("SUBJECT:"):
            subject = stripped.removeprefix("SUBJECT:").strip() or subject
        elif stripped.startswith("PREHEADER:"):
            preheader = stripped.removeprefix("PREHEADER:").strip() or preheader
        elif stripped == "BODY:":
            in_body = True
        elif in_body:
            body_lines.append(line.rstrip())

    body_text = (
        "\n".join(body_lines).strip() or newsletter.description or newsletter.draft_body_text or ""
    )

    if not body_lines and not body_text:
        return GeneratedDraft(
            status="error",
            mode="litellm",
            message=(
                "AI output could not be parsed. Expected SUBJECT:/PREHEADER:/BODY: format. "
                "Raw output was not in the expected structure."
            ),
            subject=subject,
            preheader=preheader,
            body_text=content[:500] if content else "",
        )

    return GeneratedDraft(
        status="generated",
        mode="litellm",
        message="Generated draft successfully using the configured provider.",
        subject=subject,
        preheader=preheader,
        body_text=body_text,
    )


def _strip_model_prefix(raw_model: str, provider_type: str) -> str:
    litellm_prefix = PROVIDER_TO_LITELLM_PREFIX.get(provider_type, provider_type)
    prefix_with_slash = f"{litellm_prefix}/"
    if raw_model.startswith(prefix_with_slash):
        return raw_model[len(prefix_with_slash) :]
    return raw_model


def _static_catalog_models(provider_type: str) -> list[str]:
    litellm_prefix = PROVIDER_TO_LITELLM_PREFIX.get(provider_type, provider_type)
    try:
        from litellm import models_by_provider
    except Exception:
        return []

    raw_models = models_by_provider.get(litellm_prefix, set())
    return sorted({_strip_model_prefix(m, provider_type) for m in raw_models})


def discover_models_for_provider(
    provider_type: str,
    *,
    api_key: str | None = None,
    configuration: str | None = None,
) -> list[str]:
    if api_key:
        try:
            from litellm import get_valid_models
        except Exception:
            return _static_catalog_models(provider_type)

        litellm_prefix = PROVIDER_TO_LITELLM_PREFIX.get(provider_type, provider_type)
        try:
            config = _config_from_provider_type(provider_type, configuration=configuration)
        except (ValueError, json.JSONDecodeError):
            config = {}

        try:
            live_models = get_valid_models(
                check_provider_endpoint=True,
                custom_llm_provider=litellm_prefix,
                api_key=api_key,
                api_base=config.get("api_base"),
            )
        except Exception:
            return _static_catalog_models(provider_type)

        if live_models:
            return sorted({_strip_model_prefix(m, provider_type) for m in live_models})

    return _static_catalog_models(provider_type)


def validate_provider_model(
    provider_type: str,
    model_name: str,
    api_key: str,
    *,
    configuration: str | None = None,
) -> tuple[bool, str]:
    try:
        from litellm import completion
    except Exception:
        return False, "LiteLLM is not installed."

    full_model = _resolve_full_model_name(provider_type, model_name)
    try:
        completion_kwargs = _config_from_provider_type(provider_type, configuration=configuration)
    except (ValueError, json.JSONDecodeError) as exc:
        return False, f"Invalid configuration: {exc}"

    try:
        completion(
            model=full_model,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            api_key=api_key,
            max_tokens=3,
            **completion_kwargs,
        )
    except Exception as exc:
        return False, f"Authentication or connection error: {type(exc).__name__}"

    return True, f"Model {full_model} verified successfully."


def _config_from_provider_type(
    provider_type: str,
    *,
    configuration: str | None = None,
) -> dict[str, Any]:
    config: dict[str, Any] = {}
    preset_url = PRESET_BASE_URLS.get(provider_type)
    if preset_url:
        config["api_base"] = preset_url

    if configuration:
        parsed = json.loads(configuration)
        if not isinstance(parsed, dict):
            raise ValueError("Provider configuration must be a JSON object.")
        for reserved_key in ("api_key", "messages", "model", "max_tokens"):
            parsed.pop(reserved_key, None)
        if "base_url" in parsed and "api_base" not in parsed:
            parsed["api_base"] = parsed.pop("base_url")
        config.update(parsed)

    return config


def _resolve_full_model_name(provider_type: str, model_name: str | None) -> str:
    effective = (model_name or "").strip() or "test"
    prefix = PROVIDER_TO_LITELLM_PREFIX.get(provider_type, provider_type)
    if effective.startswith(f"{prefix}/"):
        return effective
    return f"{prefix}/{effective}"


def resolve_provider_test_config(
    provider: object,
    *,
    model_name: str | None = None,
) -> tuple[str, dict[str, Any]]:
    provider_type = getattr(provider, "provider_type", "")
    full_model = _resolve_full_model_name(provider_type, model_name)
    raw_configuration = getattr(provider, "configuration", None)
    config = _config_from_provider_type(provider_type, configuration=raw_configuration)
    return full_model, config
