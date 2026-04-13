from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.crypto import decrypt_secret
from app.models import Newsletter
from app.source_pipeline.service import build_source_bundle, has_usable_source_bundle

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
SIMULATED_AI_GENERATION_ENV_VAR = "PULSE_NEWS_ALLOW_SIMULATED_AI_GENERATION"


@dataclass(frozen=True)
class ApiKeyResolution:
    api_key: str | None
    source: str
    detail: str


def _get_newsletter_provider(newsletter: Newsletter):
    from sqlalchemy import select

    from app.database import get_session_maker
    from app.models import GenerationProfile, Provider

    if newsletter.provider is not None:
        return newsletter.provider
    if newsletter.provider_id is None:
        if newsletter.generation_profile_id is None:
            return None

        session = get_session_maker()()
        try:
            profile = session.scalar(
                select(GenerationProfile).where(
                    GenerationProfile.id == newsletter.generation_profile_id
                )
            )
            if profile is None or profile.provider_id is None:
                return None
            return session.scalar(select(Provider).where(Provider.id == profile.provider_id))
        finally:
            session.close()

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
    if newsletter.generation_profile_id is not None:
        from sqlalchemy import select

        from app.database import get_session_maker
        from app.models import GenerationProfile

        session = get_session_maker()()
        try:
            profile = session.scalar(
                select(GenerationProfile).where(
                    GenerationProfile.id == newsletter.generation_profile_id
                )
            )
            if profile is not None and profile.model_name.strip():
                return profile.model_name.strip()
        finally:
            session.close()

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


def _normalize_api_key_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _environment_api_key_resolution(provider_name: str) -> ApiKeyResolution:
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

    if provider_name == "kimi":
        kimi_key = _normalize_api_key_value(os.getenv("KIMI_API_KEY"))
        if kimi_key:
            return ApiKeyResolution(
                api_key=kimi_key,
                source="environment",
                detail="Using KIMI_API_KEY environment default for provider 'kimi'.",
            )
        moonshot_key = _normalize_api_key_value(os.getenv("MOONSHOT_API_KEY"))
        if moonshot_key:
            return ApiKeyResolution(
                api_key=moonshot_key,
                source="environment",
                detail="Using MOONSHOT_API_KEY environment default for provider 'kimi'.",
            )
        return ApiKeyResolution(
            api_key=None,
            source="environment",
            detail=(
                "No explicit API key is configured for provider 'kimi'. "
                "Set KIMI_API_KEY or MOONSHOT_API_KEY."
            ),
        )

    if env_name is None:
        return ApiKeyResolution(
            api_key=None,
            source="environment",
            detail=f"No environment credential mapping exists for provider '{provider_name}'.",
        )

    env_value = _normalize_api_key_value(os.getenv(env_name))
    if env_value:
        return ApiKeyResolution(
            api_key=env_value,
            source="environment",
            detail=f"Using {env_name} environment default for provider '{provider_name}'.",
        )

    return ApiKeyResolution(
        api_key=None,
        source="environment",
        detail=(
            f"No explicit API key is configured for provider '{provider_name}'. "
            f"Set {env_name} or select an active matching API key on the newsletter."
        ),
    )


def _resolve_api_key_for_newsletter(newsletter: Newsletter) -> ApiKeyResolution:
    from sqlalchemy import select

    from app.database import get_session_maker
    from app.models import ApiKey, GenerationProfile

    provider_name = _normalized_provider_name(newsletter)
    session = get_session_maker()()

    try:
        binding_mode = "pinned_key"
        profile_api_key_id = newsletter.api_key_id
        resolution_source = "newsletter"
        if newsletter.generation_profile_id is not None:
            profile = session.scalar(
                select(GenerationProfile).where(
                    GenerationProfile.id == newsletter.generation_profile_id
                )
            )
            if profile is not None:
                binding_mode = profile.api_key_binding_mode or "pinned_key"
                profile_api_key_id = profile.api_key_id
                resolution_source = "profile"

        if binding_mode == "system_default":
            return _environment_api_key_resolution(provider_name)

        if profile_api_key_id is None:
            return ApiKeyResolution(
                api_key=None,
                source=resolution_source,
                detail=(
                    "No explicit generation API key is configured. "
                    "Select a pinned key or opt into system_default via a generation profile."
                ),
            )

        if profile_api_key_id:
            api_key = session.scalar(select(ApiKey).where(ApiKey.id == profile_api_key_id))
            if api_key is None:
                return ApiKeyResolution(
                    api_key=None,
                    source=resolution_source,
                    detail=(
                        "The selected generation API key "
                        f"(id={profile_api_key_id}) no longer exists."
                    ),
                )
            if api_key.provider_type != provider_name:
                return ApiKeyResolution(
                    api_key=None,
                    source=resolution_source,
                    detail=(
                        f"The selected newsletter API key '{api_key.name}' (id={api_key.id}) "
                        f"is for provider '{api_key.provider_type}', not '{provider_name}'."
                    ),
                )
            if not api_key.is_active:
                return ApiKeyResolution(
                    api_key=None,
                    source=resolution_source,
                    detail=(
                        f"The selected newsletter API key '{api_key.name}' (id={api_key.id}) "
                        "is inactive. Activate it or select a different key."
                    ),
                )
            if api_key.key_value:
                try:
                    decrypted_value = _normalize_api_key_value(decrypt_secret(api_key.key_value))
                except Exception:
                    return ApiKeyResolution(
                        api_key=None,
                        source=resolution_source,
                        detail=(
                            f"The selected newsletter API key '{api_key.name}' (id={api_key.id}) "
                            "could not be decrypted. Re-save the key and try again."
                        ),
                    )
                if decrypted_value:
                    return ApiKeyResolution(
                        api_key=decrypted_value,
                        source=resolution_source,
                        detail=(
                            f"Using newsletter API key '{api_key.name}' (id={api_key.id}) for "
                            f"provider '{provider_name}'."
                        ),
                    )
            return ApiKeyResolution(
                api_key=None,
                source=resolution_source,
                detail=(
                    f"The selected newsletter API key '{api_key.name}' (id={api_key.id}) is empty."
                ),
            )
    finally:
        session.close()

    return ApiKeyResolution(
        api_key=None,
        source=resolution_source,
        detail=(
            "No explicit generation API key is configured. "
            "Select a pinned key or opt into system_default via a generation profile."
        ),
    )


def _get_api_key_for_newsletter(newsletter: Newsletter) -> str | None:
    return _resolve_api_key_for_newsletter(newsletter).api_key


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


def _error_generate(newsletter: Newsletter, message: str) -> GeneratedDraft:
    return GeneratedDraft(
        status="error",
        mode="none",
        message=message,
        subject=newsletter.draft_subject or newsletter.name,
        preheader=newsletter.draft_preheader or newsletter.description or "",
        body_text=newsletter.draft_body_text or "",
    )


def _fallback_generate(newsletter: Newsletter, *, reason: str) -> GeneratedDraft:
    subject = newsletter.draft_subject.strip() or f"{newsletter.name}: generated draft"
    preheader = (
        newsletter.draft_preheader
        or newsletter.description
        or "Generated locally because explicit AI simulation is enabled."
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
            f"Generated a local simulated draft because {reason} "
            f"Simulation is explicitly enabled via {SIMULATED_AI_GENERATION_ENV_VAR}=true."
        ),
        subject=subject,
        preheader=preheader,
        body_text=body_text,
    )


def _parse_structured_generation_output(
    newsletter: Newsletter,
    *,
    content: str,
) -> GeneratedDraft | None:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    subject = str(parsed.get("subject") or newsletter.name).strip() or newsletter.name
    preheader = str(parsed.get("preheader") or newsletter.description or "").strip()
    body_text = str(parsed.get("body_markdown") or parsed.get("body_text") or "").strip()
    if not body_text:
        return GeneratedDraft(
            status="error",
            mode="litellm",
            message="AI JSON output was missing body_markdown/body_text.",
            subject=subject,
            preheader=preheader,
            body_text="",
        )

    validation_error = _validate_generated_content(
        subject=subject, preheader=preheader, body_text=body_text
    )
    if validation_error is not None:
        return GeneratedDraft(
            status="error",
            mode="litellm",
            message=validation_error,
            subject=subject,
            preheader=preheader,
            body_text=body_text,
        )

    return GeneratedDraft(
        status="generated",
        mode="litellm",
        message="Generated draft successfully using the configured provider.",
        subject=subject,
        preheader=preheader,
        body_text=body_text,
    )


def generate_newsletter_draft(newsletter: Newsletter) -> GeneratedDraft:
    provider_name = _normalized_provider_name(newsletter)
    settings = get_settings()

    # Enforce provider enabled at generation time
    provider = _get_newsletter_provider(newsletter)
    if provider is not None and not provider.is_enabled:
        return _error_generate(
            newsletter,
            f"Provider '{provider.name}' is disabled. Enable it before generating.",
        )

    if provider_name not in SUPPORTED_PROVIDERS:
        supported_providers = ", ".join(sorted(SUPPORTED_PROVIDERS))
        return _error_generate(
            newsletter,
            (
                f"Unsupported provider: '{newsletter.provider_name}'. "
                f"Supported: {supported_providers}"
            ),
        )

    credential_resolution = _resolve_api_key_for_newsletter(newsletter)
    source_bundle = build_source_bundle(newsletter)

    if not has_usable_source_bundle(source_bundle):
        return _error_generate(
            newsletter,
            (
                "No usable source material could be collected. Add at least one fetchable source "
                "URL before generating."
            ),
        )

    if completion is None:
        message = "LiteLLM is not available, so live AI generation cannot run."
        if settings.allow_simulated_ai_generation:
            return _fallback_generate(newsletter, reason=message)
        return _error_generate(newsletter, message)

    if credential_resolution.api_key is None:
        if settings.allow_simulated_ai_generation:
            return _fallback_generate(newsletter, reason=credential_resolution.detail)
        return _error_generate(newsletter, credential_resolution.detail)

    prompt = "\n".join(
        [
            f"Newsletter name: {newsletter.name}",
            f"Description: {newsletter.description or 'None'}",
            f"Audience label: {newsletter.audience_name}",
            (
                "Previous approved revision:\n"
                f"Subject: {newsletter.approved_revision.subject}\n"
                f"Preheader: {newsletter.approved_revision.preheader or ''}\n"
                f"Body: {newsletter.approved_revision.body_text[:400]}"
            )
            if getattr(newsletter, "approved_revision", None)
            else "Previous approved revision: None",
            "Source bundle:",
            *[
                (
                    f"- [{source.source_id}] {source.title}: {source.summary} ({source.url}) "
                    f"published_at={source.published_at or 'unknown'} "
                    f"relevance_score={source.relevance_score} "
                    f"dedupe_hash={source.dedupe_hash}"
                )
                for source in source_bundle
            ],
            "Generate a concise newsletter draft with:",
            "1. A subject line",
            "2. A preheader",
            "3. A plain-text newsletter body with short sections",
            "",
            f"Prompt instructions:\n{newsletter.prompt}",
            "",
            "Return strict JSON with this shape:",
            '{"subject":"...","preheader":"...","body_markdown":"...","highlights":["..."],"source_references":[{"source_id":"src_1","claim":"..."}]}',
            "Do not return prose outside JSON.",
        ]
    )

    try:
        api_key = credential_resolution.api_key
        completion_kwargs = _provider_completion_configuration(newsletter)

        # Add User-Agent header for Kimi Code API compatibility
        if _normalized_provider_name(newsletter) == "kimi":
            existing_headers = completion_kwargs.get("extra_headers", {})
            completion_kwargs["extra_headers"] = {
                **existing_headers,
                "User-Agent": os.environ.get("LITELLM_USER_AGENT", "claude-code/0.1.0"),
            }

        response = completion(
            model=_provider_model_name(newsletter),
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
            **completion_kwargs,
        )
        content = response.choices[0].message.content or ""
    except ValueError as exc:
        return _error_generate(newsletter, str(exc))
    except Exception as exc:
        detail = (
            f"Live generation failed for provider '{provider_name}': {type(exc).__name__}: {exc}"
        )
        if settings.allow_simulated_ai_generation:
            return _fallback_generate(newsletter, reason=detail)
        return _error_generate(newsletter, detail)

    structured_result = _parse_structured_generation_output(newsletter, content=content)
    if structured_result is not None:
        return structured_result

    return GeneratedDraft(
        status="error",
        mode="litellm",
        message="AI output could not be parsed as strict JSON.",
        subject=newsletter.name,
        preheader=newsletter.description or "",
        body_text=content[:500] if content else "",
    )


def _validate_generated_content(*, subject: str, preheader: str, body_text: str) -> str | None:
    if len(subject) > 120:
        return "Generated subject exceeds the 120 character limit."
    if not preheader.strip():
        return "Generated output is missing a preheader."
    if not body_text.strip():
        return "Generated output is missing the body content."
    if "{{" in body_text or "}}" in body_text or "[[" in body_text or "]]" in body_text:
        return "Generated output contains unresolved placeholder markup."
    if body_text.count("[") != body_text.count("]") or body_text.count("(") != body_text.count(")"):
        return "Generated output appears to contain malformed link markup."
    if len(re.findall(r"^#+\s", body_text, flags=re.MULTILINE)) == 0 and "- " not in body_text:
        return "Generated output is missing required section structure."
    return None


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
