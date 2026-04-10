from __future__ import annotations

import os
from dataclasses import dataclass

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


SUPPORTED_PROVIDERS = {"anthropic", "gemini", "google", "openai", "openrouter"}


def _normalized_provider_name(newsletter: Newsletter) -> str:
    return newsletter.provider_name.strip().lower()


def _provider_model_name(newsletter: Newsletter) -> str:
    provider_name = _normalized_provider_name(newsletter)
    if "/" in newsletter.model_name:
        return newsletter.model_name
    return f"{provider_name}/{newsletter.model_name}"


def _has_live_provider_credentials(provider_name: str) -> bool:
    env_by_provider = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "google": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    env_name = env_by_provider.get(provider_name.lower())
    return bool(env_name and os.getenv(env_name))


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

    if completion is None or not _has_live_provider_credentials(provider_name):
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

    try:  # pragma: no cover - live provider behavior is not exercised in automated tests
        response = completion(
            model=_provider_model_name(newsletter),
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content or ""
    except Exception as exc:  # pragma: no cover - local fallback handles unexpected live failures
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
    return GeneratedDraft(
        status="generated",
        mode="litellm",
        message="Generated draft successfully using the configured provider.",
        subject=subject,
        preheader=preheader,
        body_text=body_text,
    )
