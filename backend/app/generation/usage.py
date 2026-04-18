"""Token-usage serialization helpers.

Separated out so the main generation path doesn't have to care about
whether a usage object came from a single completion or was aggregated
across tool-loop iterations.
"""

from __future__ import annotations

import json
from typing import Any


def serialize(usage: Any) -> str | None:
    """Serialize a LiteLLM/OpenAI ``usage`` object to JSON, or return None
    when no usage info is available."""
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


def aggregate_from_trace(trace: list[dict[str, Any]], *, fallback_usage: Any = None) -> str | None:
    """Sum prompt/completion tokens across every tool-loop iteration so the
    programmatic footer reports the true cost of a generation rather than only
    the last round-trip (which, for Kimi web_search, is the smallest one)."""
    if not trace:
        return serialize(fallback_usage)

    prompt_total = 0
    completion_total = 0
    for entry in trace:
        prompt = entry.get("prompt_tokens")
        if isinstance(prompt, int):
            prompt_total += prompt
        completion_val = entry.get("completion_tokens")
        if isinstance(completion_val, int):
            completion_total += completion_val

    if prompt_total == 0 and completion_total == 0:
        return serialize(fallback_usage)

    return json.dumps(
        {
            "prompt_tokens": prompt_total,
            "completion_tokens": completion_total,
            "total_tokens": prompt_total + completion_total,
        }
    )
