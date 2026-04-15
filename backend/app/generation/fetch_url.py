"""Client-side URL fetch tool.

Companion to ``web_search``. Search returns title/url/snippet triples
— enough for the model to decide *which* source matters, but not to
quote from. Without ``fetch_url`` the model has to invent details
based on the snippet, and that's where the confabulated product
names came from in the last run.

This module is narrow and isolated: schema + executor only. No
knowledge of providers, loops, or the generation pipeline lives
here. Everything goes through stdlib so there's no new dependency.
"""

from __future__ import annotations

import json
import re
from html import unescape
from urllib import error as url_error
from urllib import request as url_request

TOOL_NAME = "fetch_url"

_DEFAULT_MAX_CHARS = 8000
_HARD_CAP_CHARS = 40000
_FETCH_TIMEOUT_SECONDS = 12
_REQUEST_USER_AGENT = (
    "Pulse-News-Bot/1.0 (+https://github.com/Jurel89/pulse-news) newsletter research fetcher"
)

TOOL_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Fetch the readable text of a single web page URL and return a "
            "cleaned-up excerpt. Use this after web_search when you need to "
            "verify a claim or quote a specific fact from a source — do not "
            "invent product names, dates, or numbers that were not present "
            "in the fetched content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Absolute http(s) URL to fetch.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": (
                        "Maximum characters of body text to return. Keep "
                        "conservative (default 8000) to avoid flooding the "
                        "context window."
                    ),
                    "default": _DEFAULT_MAX_CHARS,
                    "minimum": 500,
                    "maximum": _HARD_CAP_CHARS,
                },
            },
            "required": ["url"],
        },
    },
}


_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def _extract_title(html: str) -> str | None:
    match = _TITLE_RE.search(html)
    if not match:
        return None
    return unescape(_WHITESPACE_RE.sub(" ", match.group(1)).strip()) or None


def _html_to_text(html: str) -> str:
    """Strip scripts/styles/tags/entities from an HTML document. Not perfect
    — we're not embedding a real parser here — but good enough to give the
    model readable copy to quote from."""
    stripped = _SCRIPT_STYLE_RE.sub(" ", html)
    stripped = _TAG_RE.sub(" ", stripped)
    stripped = unescape(stripped)
    stripped = _WHITESPACE_RE.sub(" ", stripped)
    # Preserve paragraph-ish breaks but collapse runs of blank lines.
    stripped = _MULTI_NEWLINE_RE.sub("\n\n", stripped)
    return stripped.strip()


def execute(tool_name: str, arguments_json: str) -> str:
    """Run the fetch_url tool. Never raises — all error paths return a
    compact JSON string the model can use to recover."""
    if tool_name != TOOL_NAME:
        return json.dumps({"error": f"unknown tool: {tool_name}"})

    try:
        payload = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"invalid tool arguments json: {exc}"})

    url = str(payload.get("url") or "").strip()
    if not url:
        return json.dumps({"error": "missing required argument: url"})
    if not (url.startswith("http://") or url.startswith("https://")):
        return json.dumps({"error": "url must start with http:// or https://"})

    raw_max = payload.get("max_chars", _DEFAULT_MAX_CHARS)
    try:
        max_chars = max(500, min(int(raw_max), _HARD_CAP_CHARS))
    except (TypeError, ValueError):
        max_chars = _DEFAULT_MAX_CHARS

    req = url_request.Request(
        url,
        headers={
            "User-Agent": _REQUEST_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
        },
    )
    try:
        with url_request.urlopen(req, timeout=_FETCH_TIMEOUT_SECONDS) as response:
            status = response.status
            content_type = (response.headers.get("Content-Type") or "").lower()
            raw_bytes = response.read(_HARD_CAP_CHARS * 4)
    except url_error.HTTPError as exc:
        return json.dumps({"error": f"http {exc.code}: {exc.reason}", "url": url})
    except url_error.URLError as exc:
        return json.dumps({"error": f"url error: {exc.reason}", "url": url})
    except TimeoutError:
        return json.dumps({"error": "timeout", "url": url})
    except Exception as exc:
        return json.dumps({"error": f"fetch failed: {type(exc).__name__}: {exc}", "url": url})

    # Decode — be tolerant of bad encodings; the model can handle utf-8 replacement.
    charset_match = re.search(r"charset=([\w-]+)", content_type)
    encoding = (charset_match.group(1).lower() if charset_match else "utf-8").strip()
    try:
        raw_text = raw_bytes.decode(encoding, errors="replace")
    except LookupError:
        raw_text = raw_bytes.decode("utf-8", errors="replace")

    title: str | None = None
    if "html" in content_type or raw_text.lstrip().startswith("<"):
        title = _extract_title(raw_text)
        body = _html_to_text(raw_text)
    else:
        body = raw_text

    truncated = body[:max_chars]
    was_truncated = len(body) > max_chars

    return json.dumps(
        {
            "url": url,
            "status": status,
            "title": title,
            "content": truncated,
            "truncated": was_truncated,
        }
    )
