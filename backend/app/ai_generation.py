from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

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
    if "/" in model_name:
        return model_name
    return f"{provider_name}/{model_name}"


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
                return api_key.key_value

        active_provider_key = session.scalar(
            select(ApiKey)
            .where(
                ApiKey.provider_type == provider_name,
                ApiKey.is_active.is_(True),
            )
            .order_by(ApiKey.updated_at.desc(), ApiKey.id.desc())
        )
        if active_provider_key and active_provider_key.key_value:
            return active_provider_key.key_value
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
        return os.getenv(env_name)
    return None


def _has_live_provider_credentials(newsletter: Newsletter) -> bool:
    return _get_api_key_for_newsletter(newsletter) is not None


def _provider_completion_configuration(newsletter: Newsletter) -> dict[str, Any]:
    provider = _get_newsletter_provider(newsletter)
    provider_name = _normalized_provider_name(newsletter)

    PRESET_BASE_URLS = {
        "zai": "https://api.z.ai/api/paas/v4/",
        "kimi": "https://api.moonshot.ai/v1",
    }

    config: dict[str, Any] = {}

    preset_url = PRESET_BASE_URLS.get(provider_name)
    if preset_url:
        config["api_base"] = preset_url

    if provider is not None and provider.configuration:
        try:
            configuration = json.loads(provider.configuration)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Provider configuration must be valid JSON: {exc.msg}.") from exc

        if not isinstance(configuration, dict):
            raise ValueError("Provider configuration must be a JSON object.")

        for reserved_key in ("api_key", "messages", "model"):
            configuration.pop(reserved_key, None)
        config.update(configuration)

    return config


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
