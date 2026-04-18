"""Forgiving JSON parser for AI generation output.

Models love to wrap their JSON in markdown fences, add a polite
preface (\"Here is the newsletter:\"), or trail off with a closing
remark. Strict ``json.loads`` rejects all of that. This module
strips fences and falls back to extracting the outermost balanced
``{...}`` substring before giving up.

Kept deliberately narrow — no knowledge of providers, newsletters,
or the generation pipeline lives here. Pure string in, parsed dict
or None out.
"""

from __future__ import annotations

import json
import re

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)


def strip_json_fences(content: str) -> str:
    """Strip markdown code fences around JSON so models that wrap output still parse."""
    stripped = content.strip()
    match = _JSON_FENCE_RE.match(stripped)
    if match is not None:
        return match.group(1).strip()
    return stripped


def extract_json_object_substring(content: str) -> str | None:
    """Return the largest ``{...}`` substring in ``content`` so we can
    rescue a strict-JSON payload even when the model wraps it in prose or
    bullets. Returns None when no braced object is found."""
    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
        return None
    return content[first_brace : last_brace + 1]


def parse_json_loose(content: str) -> dict | None:
    """Try to parse ``content`` as JSON, tolerating markdown fences and
    surrounding prose. Returns the parsed dict on success, or None if the
    content cannot be recovered as a JSON object.

    Non-dict top-level values (arrays, strings) are intentionally treated as
    None — newsletters expect ``{subject, preheader, body_markdown}``.
    """
    stripped = strip_json_fences(content)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        candidate = extract_json_object_substring(stripped)
        if candidate is None:
            return None
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def validate_generated_content(*, subject: str, preheader: str, body_text: str) -> str | None:
    """Return an error message if the generated fields fail our newsletter
    guardrails, or None when the content is acceptable.

    Kept deliberately narrow. ``body_text`` is free-form markdown written by
    the model — characters like ``{{``, ``}}``, ``[[``, ``]]`` can legitimately
    appear (footnote references, code snippets, Obsidian-style links) and the
    email-rendering path HTML-escapes them anyway, so they cannot break
    output. Previously we rejected the entire generation on those characters,
    which meant discarding a 15-round search-grounded newsletter over a
    single ``[[1]]`` citation marker. Don't do that again.

    We still reject the real unsubscribe/recipient substitution tokens,
    because those *are* leaked templating that would confuse recipients.
    """
    if len(subject) > 120:
        return "Generated subject exceeds the 120 character limit."
    if not preheader.strip():
        return "Generated output is missing a preheader."
    if not body_text.strip():
        return "Generated output is missing the body content."
    if "%recipient_" in body_text or "%unsubscribe_" in body_text:
        return "Generated output contains unsupported template variables."
    return None
