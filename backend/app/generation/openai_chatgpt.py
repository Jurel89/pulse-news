"""ChatGPT Responses-API generation adapter.

Routes generation through https://chatgpt.com/backend-api/codex/responses
via direct httpx — LiteLLM does not speak this endpoint.

The operator's OAuth access token is used directly; the token is refreshed
when it is within 300 s of expiry so the caller never sends an expired token.

SSE is consumed server-side: we collect ``output_text.delta`` fragments and
return a single string so the rest of the generation pipeline stays
non-streaming.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

logger = logging.getLogger(__name__)

# Models known to work on this backend.  Requests with any other model ID
# are silently normalised to the safe default so we avoid 400 errors.
_SUPPORTED_MODELS = frozenset(
    [
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.3-codex",
        "gpt-5.2",
    ]
)
_DEFAULT_MODEL = "gpt-5.4"
_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
_HTTP_TIMEOUT = httpx.Timeout(120.0)  # SSE streams can be slow to complete


@dataclass
class ChatGPTGenerationResult:
    content: str
    token_usage_json: str | None = None
    raw_response_hash: str | None = None
    tool_loop_trace_json: str | None = None
    annotations: list[dict] = field(default_factory=list)
    normalized_model: str | None = None


class ChatGPTGenerationError(Exception):
    """Raised when the ChatGPT Responses API returns an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _normalize_model(model: str) -> str:
    if model in _SUPPORTED_MODELS:
        return model
    raise ChatGPTGenerationError(
        f"Model '{model}' is not supported for ChatGPT subscription. "
        f"Supported models: {', '.join(sorted(_SUPPORTED_MODELS))}."
    )


def _build_request_body(
    *,
    model: str,
    prompt: str,
    web_search: bool,
) -> dict:
    body: dict = {
        "model": model,
        "instructions": "You are a helpful newsletter writing assistant.",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
        "stream": True,
        "store": False,
        "include": ["reasoning.encrypted_content"],
        "reasoning": {"effort": "medium", "summary": "auto"},
        "text": {"verbosity": "medium"},
        "parallel_tool_calls": False,
    }
    if web_search:
        body["tools"] = [{"type": "web_search"}]
    return body


def _parse_sse_stream(response: httpx.Response) -> tuple[str, list[dict], dict | None]:
    """Consume an SSE response and return (assembled_text, annotations, usage).

    Parses ``response.output_text.delta`` events to build the final string.
    Captures ``url_citation`` annotations.
    Captures usage from a ``response.completed`` event.
    """
    text_parts: list[str] = []
    annotations: list[dict] = []
    usage: dict | None = None

    for raw_line in response.iter_lines():
        line = raw_line.strip()
        if not line or not line.startswith("data:"):
            continue
        payload_str = line[5:].strip()
        if payload_str in ("[DONE]", ""):
            continue
        try:
            event = json.loads(payload_str)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type", "")

        if event_type == "response.output_text.delta":
            delta = event.get("delta", "")
            if delta:
                text_parts.append(delta)

        elif event_type == "response.output_text.annotation.added":
            ann = event.get("annotation")
            if ann:
                annotations.append(ann)

        elif event_type == "response.completed":
            resp_obj = event.get("response", {})
            usage = resp_obj.get("usage")
            # Also grab any output_text from the completed snapshot as fallback.
            if not text_parts:
                for out_item in resp_obj.get("output", []):
                    for content in out_item.get("content", []):
                        if content.get("type") == "output_text":
                            text_parts.append(content.get("text", ""))

    return "".join(text_parts), annotations, usage


def generate(
    *,
    api_key_row,
    prompt: str,
    model: str,
    web_search: bool,
    db_session,
) -> ChatGPTGenerationResult:
    """Generate newsletter content via ChatGPT Responses API.

    Refreshes the OAuth token when it is within 300 s of expiry.
    ``api_key_row`` must be an ``ApiKey`` model instance with ``auth_type == "oauth"``.
    """
    from app.crypto import decrypt_secret, encrypt_secret
    from app.oauth import openai_chatgpt as _oauth

    # --- Token freshness check ---
    # SQLite returns naive datetimes even though we stored timezone-aware values;
    # treat naive oauth_expires_at as UTC so the comparison below doesn't raise.
    now = datetime.now(UTC)
    expires_at = api_key_row.oauth_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    near_expiry = expires_at is None or now >= (expires_at - _timedelta_300s())
    if near_expiry:
        logger.info("OAuth token near expiry; refreshing before generation.")
        try:
            raw_refresh = decrypt_secret(api_key_row.oauth_refresh_token)
            bundle = _oauth.refresh(raw_refresh)
            api_key_row.oauth_access_token = encrypt_secret(bundle.access_token)
            api_key_row.oauth_refresh_token = encrypt_secret(bundle.refresh_token)
            api_key_row.oauth_expires_at = bundle.expires_at
            if bundle.account_id:
                api_key_row.oauth_account_id = bundle.account_id
            if bundle.plan_type:
                api_key_row.oauth_plan_type = bundle.plan_type
            db_session.add(api_key_row)
            db_session.commit()
            logger.info("OAuth token refreshed; new expiry=%s", bundle.expires_at)
        except Exception as exc:
            logger.error("OAuth token refresh failed: %s", exc)
            raise ChatGPTGenerationError(f"OAuth token refresh failed: {exc}") from exc

    try:
        access_token = decrypt_secret(api_key_row.oauth_access_token)
    except Exception as exc:
        raise ChatGPTGenerationError(f"Could not decrypt OAuth access token: {exc}") from exc

    account_id = api_key_row.oauth_account_id or ""
    effective_model = _normalize_model(model)
    body = _build_request_body(model=effective_model, prompt=prompt, web_search=web_search)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "chatgpt-account-id": account_id,
        "OpenAI-Beta": "responses=experimental",
        "originator": "codex_cli_rs",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            with client.stream("POST", _RESPONSES_URL, headers=headers, json=body) as response:
                if response.status_code not in (200, 201):
                    body_preview = response.read()[:400].decode("utf-8", errors="replace")
                    is_rate_limit = (
                        response.status_code == 429 or "usage_limit_reached" in body_preview
                    )
                    if is_rate_limit:
                        raise ChatGPTGenerationError(
                            f"ChatGPT rate limit or usage cap reached "
                            f"(HTTP {response.status_code}). "
                            "Check your ChatGPT plan limits and try again later.",
                            status_code=response.status_code,
                        )
                    raise ChatGPTGenerationError(
                        f"ChatGPT Responses API returned "
                        f"HTTP {response.status_code}: {body_preview}",
                        status_code=response.status_code,
                    )
                content, annotations, usage = _parse_sse_stream(response)
    except ChatGPTGenerationError:
        raise
    except Exception as exc:
        raise ChatGPTGenerationError(
            f"ChatGPT Responses API request failed: {type(exc).__name__}: {exc}"
        ) from exc

    raw_hash = hashlib.sha256(content.encode()).hexdigest()
    token_usage_json = json.dumps(usage) if usage else None

    return ChatGPTGenerationResult(
        content=content,
        token_usage_json=token_usage_json,
        raw_response_hash=raw_hash,
        annotations=annotations,
        normalized_model=effective_model if effective_model != model else None,
    )


def _timedelta_300s():
    from datetime import timedelta

    return timedelta(seconds=300)
