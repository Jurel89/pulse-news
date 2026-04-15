"""Client-side web-search tool.

The Kimi Coding API (api.kimi.com/coding/v1) — the only endpoint our
users' subscription grants access to — has no server-resolved web
search builtin. That pattern only exists on api.moonshot.ai/v1. To
give Kimi real-time web access we follow what the official Kimi CLI
does: declare a plain client-side ``web_search`` function tool, let
the model request it via ``tool_calls``, then execute the search
ourselves (DDG, via the keyless ``ddgs`` package) and feed the
results back on the next turn.

This module is deliberately narrow: schema + executor. No knowledge
of providers, loops, or the generation pipeline lives here.
"""

from __future__ import annotations

import json

TOOL_NAME = "web_search"

TOOL_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Search the open web and return the most relevant recent results. "
            "Use this before writing the newsletter so every claim is grounded in "
            "real, citable sources from the last few days. Call it multiple times "
            "with different queries when you need broader coverage."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Keep it specific and keyword-rich.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results to return (1-10).",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        },
    },
}


def execute(tool_name: str, arguments_json: str) -> str:
    """Run the client-side tool and return a string suitable for a
    ``role=tool`` message. Never raises — malformed input and network
    failures come back as error JSON so the model can recover."""
    if tool_name != TOOL_NAME:
        return json.dumps({"error": f"unknown tool: {tool_name}"})

    try:
        payload = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"invalid tool arguments json: {exc}"})

    query = str(payload.get("query") or "").strip()
    if not query:
        return json.dumps({"error": "missing required argument: query"})

    raw_max = payload.get("max_results", 5)
    try:
        max_results = max(1, min(int(raw_max), 10))
    except (TypeError, ValueError):
        max_results = 5

    try:
        from ddgs import DDGS
    except ImportError:  # pragma: no cover - ddgs is a hard dependency
        return json.dumps({"error": "ddgs package is not installed"})

    try:
        with DDGS() as ddg:
            raw_results = list(ddg.text(query, max_results=max_results))
    except Exception as exc:
        return json.dumps({"error": f"search failed: {type(exc).__name__}: {exc}"})

    normalized = [
        {
            "title": (item.get("title") or "").strip(),
            "url": (item.get("href") or item.get("url") or "").strip(),
            "snippet": (item.get("body") or item.get("snippet") or "").strip(),
        }
        for item in raw_results
        if isinstance(item, dict)
    ]
    return json.dumps({"query": query, "results": normalized})
