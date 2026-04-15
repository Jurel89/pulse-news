from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any

from app.crypto import decrypt_secret
from app.models import Newsletter

try:  # pragma: no cover - exercised conditionally when dependency is present and configured
    from litellm import completion
except Exception:  # pragma: no cover - local fallback path handles absence
    completion = None


@dataclass
class GeneratedContent:
    status: str
    mode: str
    message: str
    subject: str
    preheader: str
    body_text: str
    provider_snapshot_json: str | None = None
    token_usage_json: str | None = None
    raw_response_hash: str | None = None


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


def _provider_web_search_tools(provider_name: str) -> list[dict] | None:
    """Return the provider-specific tool payload that enables real-time web
    search on the generation call, or None if the provider has no supported
    server-resolved web-search tool.

    This is a newsletter platform — giving the model web access by default is
    the only way content stays current. Client-resolved tool loops (OpenAI
    Responses API, OpenRouter `:online` routing) are intentionally left out of
    this v1 because they need separate plumbing.
    """
    normalized = provider_name.lower()
    if normalized in {"kimi", "moonshot"}:
        # Moonshot's server-resolved $web_search builtin works via both the
        # Moonshot chat API and the Kimi Code API (api.kimi.com/coding/v1).
        return [{"type": "builtin_function", "function": {"name": "$web_search"}}]
    if normalized == "anthropic":
        # Claude native server-side web search tool.
        return [{"type": "web_search_20250305", "name": "web_search"}]
    if normalized in {"gemini", "google"}:
        # Gemini grounding via Google Search; LiteLLM forwards this tool shape
        # to the Gemini API which resolves the search server-side.
        return [{"google_search": {}}]
    return None


@dataclass(frozen=True)
class ApiKeyResolution:
    api_key: str | None
    source: str
    detail: str


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
    from app.models import ApiKey

    provider_name = _normalized_provider_name(newsletter)
    if newsletter.api_key_id is None:
        return _environment_api_key_resolution(provider_name)

    session = get_session_maker()()

    try:
        api_key = session.scalar(select(ApiKey).where(ApiKey.id == newsletter.api_key_id))
        if api_key is None:
            return ApiKeyResolution(
                api_key=None,
                source="newsletter",
                detail=(
                    "The selected generation API key "
                    f"(id={newsletter.api_key_id}) no longer exists."
                ),
            )
        if api_key.provider_type != provider_name:
            return ApiKeyResolution(
                api_key=None,
                source="newsletter",
                detail=(
                    f"The selected newsletter API key '{api_key.name}' (id={api_key.id}) "
                    f"is for provider '{api_key.provider_type}', not '{provider_name}'."
                ),
            )
        if not api_key.is_active:
            return ApiKeyResolution(
                api_key=None,
                source="newsletter",
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
                    source="newsletter",
                    detail=(
                        f"The selected newsletter API key '{api_key.name}' (id={api_key.id}) "
                        "could not be decrypted. Re-save the key and try again."
                    ),
                )
            if decrypted_value:
                return ApiKeyResolution(
                    api_key=decrypted_value,
                    source="newsletter",
                    detail=(
                        f"Using newsletter API key '{api_key.name}' (id={api_key.id}) for "
                        f"provider '{provider_name}'."
                    ),
                )
        return ApiKeyResolution(
            api_key=None,
            source="newsletter",
            detail=(
                f"The selected newsletter API key '{api_key.name}' (id={api_key.id}) is empty."
            ),
        )
    finally:
        session.close()


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


def _error_generate(newsletter: Newsletter, message: str) -> GeneratedContent:
    return GeneratedContent(
        status="error",
        mode="none",
        message=message,
        subject=newsletter.subject or newsletter.name,
        preheader=newsletter.preheader or newsletter.description or "",
        body_text=newsletter.body_text or "",
        provider_snapshot_json=_provider_snapshot_json(newsletter),
    )


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)


def _strip_json_fences(content: str) -> str:
    """Strip markdown code fences around JSON so models that wrap output still parse."""
    stripped = content.strip()
    match = _JSON_FENCE_RE.match(stripped)
    if match is not None:
        return match.group(1).strip()
    return stripped


def _parse_structured_generation_output(
    newsletter: Newsletter,
    *,
    content: str,
) -> GeneratedContent | None:
    try:
        parsed = json.loads(_strip_json_fences(content))
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    subject = str(parsed.get("subject") or newsletter.name).strip() or newsletter.name
    preheader = str(parsed.get("preheader") or newsletter.description or "").strip()
    body_text = str(parsed.get("body_markdown") or "").strip()
    if not body_text:
        return GeneratedContent(
            status="error",
            mode="litellm",
            message="AI JSON output was missing body_markdown.",
            subject=subject,
            preheader=preheader,
            body_text="",
            provider_snapshot_json=_provider_snapshot_json(newsletter),
        )

    validation_error = _validate_generated_content(
        subject=subject, preheader=preheader, body_text=body_text
    )
    if validation_error is not None:
        return GeneratedContent(
            status="error",
            mode="litellm",
            message=validation_error,
            subject=subject,
            preheader=preheader,
            body_text=body_text,
            provider_snapshot_json=_provider_snapshot_json(newsletter),
        )

    return GeneratedContent(
        status="generated",
        mode="litellm",
        message="Generated content successfully using the configured provider.",
        subject=subject,
        preheader=preheader,
        body_text=body_text,
        provider_snapshot_json=_provider_snapshot_json(newsletter),
    )


def generate_newsletter_content(newsletter: Newsletter, *, db_session=None) -> GeneratedContent:
    provider_name = _normalized_provider_name(newsletter)

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

    if completion is None:
        return _error_generate(
            newsletter, "LiteLLM is not available, so live AI generation cannot run."
        )

    if credential_resolution.api_key is None:
        return _error_generate(newsletter, credential_resolution.detail)

    prompt = "\n".join(
        [
            "You are writing a newsletter.",
            "",
            f"Newsletter name: {newsletter.name}",
            f"Description: {newsletter.description or 'None'}",
            f"Audience: {newsletter.audience_name}",
            "",
            "Instructions:",
            newsletter.prompt or "",
            "",
            "Write the newsletter with:",
            "1. A subject line",
            "2. A preheader",
            "3. A body in markdown format",
            "",
            "Return strict JSON with this shape:",
            '{"subject":"...","preheader":"...","body_markdown":"..."}',
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

        # Always enable web search when the provider supports it. This is a
        # newsletter platform — without real-time web access the model just
        # hallucinates "recent" news from training data.
        web_search_tools = _provider_web_search_tools(provider_name)
        if web_search_tools is not None:
            completion_kwargs.setdefault("tools", web_search_tools)

        response = completion(
            model=_provider_model_name(newsletter),
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
            **completion_kwargs,
        )
        content = response.choices[0].message.content or ""
        token_usage_json = _serialize_token_usage(getattr(response, "usage", None))
        raw_response_hash = hashlib.sha256(content.encode()).hexdigest()
    except ValueError as exc:
        return _error_generate(newsletter, str(exc))
    except Exception as exc:
        detail = (
            f"Live generation failed for provider '{provider_name}': {type(exc).__name__}: {exc}"
        )
        return _error_generate(newsletter, detail)

    structured_result = _parse_structured_generation_output(
        newsletter,
        content=content,
    )
    if structured_result is not None:
        structured_result.token_usage_json = token_usage_json
        structured_result.raw_response_hash = raw_response_hash
        return structured_result

    return GeneratedContent(
        status="error",
        mode="litellm",
        message="AI output could not be parsed as strict JSON.",
        subject=newsletter.name,
        preheader=newsletter.description or "",
        body_text=content[:500] if content else "",
        provider_snapshot_json=_provider_snapshot_json(newsletter),
        token_usage_json=token_usage_json,
        raw_response_hash=raw_response_hash,
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
    if "%recipient_" in body_text or "%unsubscribe_" in body_text:
        return "Generated output contains unsupported template variables."
    return None


def _provider_snapshot_json(newsletter: Newsletter) -> str:
    return json.dumps(
        {
            "provider_name": _normalized_provider_name(newsletter),
            "model_name": _provider_model_name(newsletter),
        }
    )


def _serialize_token_usage(usage: Any) -> str | None:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return json.dumps(usage)

    data = {
        key: value
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if isinstance((value := getattr(usage, key, None)), (int, float))
    }
    return json.dumps(data) if data else None


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
