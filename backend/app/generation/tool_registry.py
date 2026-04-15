"""Provider → web-search tool-schema dispatch.

Different AI providers expect wildly different tool shapes. Keeping the
mapping in one place (rather than inline in the generation pipeline)
makes it obvious where to add a new provider.

Every supported provider is a newsletter platform first-class citizen:
we want web access on by default, no per-newsletter toggle.
"""

from __future__ import annotations

from app.generation import fetch_url, web_search


def web_search_tools_for(provider_name: str) -> list[dict] | None:
    """Return the provider-specific tool payload that enables real-time web
    search, or None if the provider has no supported path.

    - **Kimi (api.kimi.com/coding/v1)** has no server-resolved web search.
      Declare a plain client-side ``web_search`` function tool; the caller
      must execute the search itself and feed results back via the tool loop.
      The Moonshot ``$web_search`` builtin only works against
      ``api.moonshot.ai/v1``, which Kimi Coding subscriptions do not grant.
    - **Anthropic Claude** has a true server-resolved tool that runs the
      search on Anthropic's side and returns final content in one round.
    - **Gemini** grounds via Google Search, also server-side / one-shot.

    OpenAI, OpenRouter and Z.ai are deferred — each needs its own path.
    """
    normalized = provider_name.lower()
    if normalized in {"kimi", "moonshot"}:
        return [web_search.TOOL_SCHEMA, fetch_url.TOOL_SCHEMA]
    if normalized == "anthropic":
        return [{"type": "web_search_20250305", "name": "web_search"}]
    if normalized in {"gemini", "google"}:
        return [{"google_search": {}}]
    return None


def requires_client_side_resolution(provider_name: str) -> bool:
    """True when the provider's tool calls must be executed by us, client-side
    (Kimi Coding API). False when the provider server-resolves in one round
    (Anthropic, Gemini) or has no tool support at all."""
    return provider_name.lower() in {"kimi", "moonshot"}
