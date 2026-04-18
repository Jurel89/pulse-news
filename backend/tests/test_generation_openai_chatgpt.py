"""Tests for the ChatGPT Responses-API generation adapter.

All upstream HTTP calls are stubbed so no real network traffic is made.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from app.generation.openai_chatgpt import (
    _build_request_body,
    _normalize_model,
    _parse_sse_stream,
    generate,
)

# ---------------------------------------------------------------------------
# Model normalisation
# ---------------------------------------------------------------------------


def test_normalize_model_known_passes_through():
    assert _normalize_model("gpt-5.4") == "gpt-5.4"
    assert _normalize_model("gpt-5.4-mini") == "gpt-5.4-mini"
    assert _normalize_model("gpt-5.3-codex") == "gpt-5.3-codex"
    assert _normalize_model("gpt-5.2") == "gpt-5.2"


def test_normalize_model_unknown_maps_to_default():
    assert _normalize_model("gpt-5.1") == "gpt-5.4"
    assert _normalize_model("unknown-model") == "gpt-5.4"


# ---------------------------------------------------------------------------
# Request body builder
# ---------------------------------------------------------------------------


def test_build_request_body_required_flags():
    body = _build_request_body(model="gpt-5.1", prompt="hello", web_search=False)
    assert body["store"] is False
    assert body["stream"] is True
    assert "reasoning.encrypted_content" in body["include"]
    assert "tools" not in body


def test_build_request_body_web_search():
    body = _build_request_body(model="gpt-5.1", prompt="hello", web_search=True)
    assert any(t.get("type") == "web_search" for t in body["tools"])


def test_build_request_body_no_max_tokens():
    body = _build_request_body(model="gpt-5.1", prompt="hello", web_search=False)
    assert "max_output_tokens" not in body
    assert "max_completion_tokens" not in body


# ---------------------------------------------------------------------------
# SSE parser
# ---------------------------------------------------------------------------


def _make_sse_lines(*events: dict) -> list[str]:
    lines = []
    for event in events:
        lines.append(f"data: {json.dumps(event)}")
        lines.append("")
    return lines


def test_parse_sse_stream_assembles_deltas():
    mock_response = MagicMock()
    mock_response.iter_lines.return_value = _make_sse_lines(
        {"type": "response.output_text.delta", "delta": "Hello"},
        {"type": "response.output_text.delta", "delta": " world"},
        {"type": "response.completed", "response": {"usage": {"total_tokens": 10}}},
    )

    text, annotations, usage = _parse_sse_stream(mock_response)

    assert text == "Hello world"
    assert annotations == []
    assert usage == {"total_tokens": 10}


def test_parse_sse_stream_captures_annotations():
    mock_response = MagicMock()
    annotation = {"type": "url_citation", "url": "https://example.com", "title": "Test"}
    mock_response.iter_lines.return_value = _make_sse_lines(
        {"type": "response.output_text.delta", "delta": "text"},
        {"type": "response.output_text.annotation.added", "annotation": annotation},
    )

    _, annotations, _ = _parse_sse_stream(mock_response)
    assert len(annotations) == 1
    assert annotations[0]["url"] == "https://example.com"


# ---------------------------------------------------------------------------
# generate() — full path
# ---------------------------------------------------------------------------


def _make_api_key_row(*, near_expiry: bool = False, expired: bool = False):
    """Build a mock ApiKey row."""
    from app.crypto import encrypt_secret

    row = MagicMock()
    row.oauth_account_id = "acct_test"
    row.oauth_refresh_token = encrypt_secret("refresh_tok")
    row.oauth_access_token = encrypt_secret("access_tok")
    if expired:
        row.oauth_expires_at = datetime.now(UTC) - timedelta(hours=1)
    elif near_expiry:
        row.oauth_expires_at = datetime.now(UTC) + timedelta(seconds=100)
    else:
        row.oauth_expires_at = datetime.now(UTC) + timedelta(hours=1)
    return row


def _mock_streaming_context(text_deltas: list[str], status_code: int = 200):
    """Returns a context manager mock that yields a response whose iter_lines emits SSE."""
    lines = []
    for delta in text_deltas:
        lines.append(f"data: {json.dumps({'type': 'response.output_text.delta', 'delta': delta})}")
        lines.append("")
    lines.append('data: {"type": "response.completed", "response": {"usage": {"total_tokens": 5}}}')
    lines.append("")

    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.iter_lines = MagicMock(return_value=lines)

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_response)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def test_generate_correct_url_headers_body():
    api_key_row = _make_api_key_row()
    db_session = MagicMock()

    captured = {}

    def fake_stream(method, url, headers=None, json=None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _mock_streaming_context(['{"subject":"S","preheader":"P","body_markdown":"B"}'])

    with patch("app.generation.openai_chatgpt.httpx.Client") as MockClient:
        mock_client_instance = MagicMock()
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_instance.stream = fake_stream
        MockClient.return_value = mock_client_instance

        generate(
            api_key_row=api_key_row,
            prompt="test prompt",
            model="gpt-5.4",
            web_search=True,
            db_session=db_session,
        )

    assert captured["url"] == "https://chatgpt.com/backend-api/codex/responses"
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert captured["headers"]["chatgpt-account-id"] == "acct_test"
    assert captured["headers"]["OpenAI-Beta"] == "responses=experimental"
    assert captured["headers"]["originator"] == "codex_cli_rs"
    assert captured["headers"]["Accept"] == "text/event-stream"
    assert captured["json"]["store"] is False
    assert captured["json"]["stream"] is True
    assert "reasoning.encrypted_content" in captured["json"]["include"]
    assert any(t.get("type") == "web_search" for t in captured["json"].get("tools", []))


def test_generate_normalizes_unknown_model():
    api_key_row = _make_api_key_row()
    db_session = MagicMock()
    captured_model = {}

    def fake_stream(method, url, headers=None, json=None):
        captured_model["model"] = json["model"]
        return _mock_streaming_context(['{"subject":"S","preheader":"P","body_markdown":"B"}'])

    with patch("app.generation.openai_chatgpt.httpx.Client") as MockClient:
        mock_client_instance = MagicMock()
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_instance.stream = fake_stream
        MockClient.return_value = mock_client_instance

        result = generate(
            api_key_row=api_key_row,
            prompt="test",
            model="gpt-4-turbo",  # unknown model
            web_search=False,
            db_session=db_session,
        )

    assert captured_model["model"] == "gpt-5.4"
    assert result.normalized_model == "gpt-5.4"


def test_generate_refreshes_near_expired_token():
    from app.oauth.openai_chatgpt import TokenBundle

    api_key_row = _make_api_key_row(near_expiry=True)
    db_session = MagicMock()

    new_bundle = TokenBundle(
        access_token="new_access",
        refresh_token="new_refresh",
        expires_at=datetime.now(UTC) + timedelta(hours=2),
        account_id="acct_test",
        plan_type="plus",
        id_token=None,
    )

    def fake_stream(method, url, headers=None, json=None):
        return _mock_streaming_context(['{"subject":"S","preheader":"P","body_markdown":"B"}'])

    with (
        patch("app.generation.openai_chatgpt.httpx.Client") as MockClient,
        patch("app.oauth.openai_chatgpt.refresh", return_value=new_bundle),
    ):
        mock_client_instance = MagicMock()
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_instance.stream = fake_stream
        MockClient.return_value = mock_client_instance

        generate(
            api_key_row=api_key_row,
            prompt="test",
            model="gpt-5.4",
            web_search=False,
            db_session=db_session,
        )

    # Refresh should have been persisted
    db_session.add.assert_called()
    db_session.commit.assert_called()
