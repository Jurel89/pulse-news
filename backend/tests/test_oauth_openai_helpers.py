"""Unit tests for app.oauth.openai_chatgpt helper functions.

All upstream HTTP calls are stubbed via httpx.MockTransport so no real network
traffic is made.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.oauth.openai_chatgpt import (
    OpenAIOAuthError,
    build_authorize_url,
    device_code_poll,
    device_code_start,
    extract_account_id,
    extract_plan_type,
    generate_pkce,
    parse_jwt_payload,
    refresh,
)

# ---------------------------------------------------------------------------
# PKCE
# ---------------------------------------------------------------------------


def test_pkce_challenge_is_sha256_of_verifier():
    verifier, challenge = generate_pkce()
    # challenge must be base64url(sha256(verifier)) with no padding
    expected_bytes = hashlib.sha256(verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(expected_bytes).rstrip(b"=").decode("ascii")
    assert challenge == expected


def test_pkce_verifier_is_url_safe_no_padding():
    verifier, _ = generate_pkce()
    assert "=" not in verifier
    assert "+" not in verifier
    assert "/" not in verifier


def test_build_authorize_url_contains_required_params():
    url = build_authorize_url(
        state="abc", challenge="xyz", redirect_uri="http://localhost:1455/auth/callback"
    )
    assert "code_challenge=xyz" in url
    assert "state=abc" in url
    assert "code_challenge_method=S256" in url
    assert "originator=codex_cli_rs" in url


# ---------------------------------------------------------------------------
# JWT parsing
# ---------------------------------------------------------------------------


def _make_jwt(payload: dict) -> str:
    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    header = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    body = b64(json.dumps(payload).encode())
    return f"{header}.{body}.fakesig"


def test_parse_jwt_payload_extracts_claims():
    payload = {
        "sub": "user123",
        "https://api.openai.com/auth": {
            "chatgpt_account_id": "acct_abc",
            "chatgpt_plan_type": "plus",
        },
    }
    token = _make_jwt(payload)
    parsed = parse_jwt_payload(token)
    assert parsed["sub"] == "user123"
    assert parsed["https://api.openai.com/auth"]["chatgpt_account_id"] == "acct_abc"


def test_extract_account_id():
    payload = {
        "https://api.openai.com/auth": {
            "chatgpt_account_id": "acct_xyz",
            "chatgpt_plan_type": "pro",
        }
    }
    assert extract_account_id(payload) == "acct_xyz"


def test_extract_plan_type():
    payload = {
        "https://api.openai.com/auth": {
            "chatgpt_account_id": "acct_xyz",
            "chatgpt_plan_type": "pro",
        }
    }
    assert extract_plan_type(payload) == "pro"


def test_extract_account_id_missing_namespace():
    assert extract_account_id({}) is None


# ---------------------------------------------------------------------------
# device_code_start
# ---------------------------------------------------------------------------


def _mock_transport_response(status_code: int, json_body: dict):
    """Return an httpx.MockTransport that always returns the given response."""

    def handler(request):
        return httpx.Response(
            status_code=status_code,
            json=json_body,
        )

    return httpx.MockTransport(handler)


def test_device_code_start_success(monkeypatch):
    response_data = {
        "device_auth_id": "dev_123",
        "user_code": "ABCD-1234",
        "interval": 5,
        "expires_in": 900,
        "verification_uri": "https://auth.openai.com/codex/device",
    }

    def fake_post(*args, **kwargs):
        return httpx.Response(200, json=response_data)

    with patch("app.oauth.openai_chatgpt.httpx.Client") as MockClient:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post = MagicMock(return_value=httpx.Response(200, json=response_data))
        MockClient.return_value = mock_instance

        result = device_code_start()

    assert result.device_auth_id == "dev_123"
    assert result.user_code == "ABCD-1234"
    assert result.interval == 5


def test_device_code_start_failure(monkeypatch):
    with patch("app.oauth.openai_chatgpt.httpx.Client") as MockClient:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post = MagicMock(return_value=httpx.Response(500, text="Internal error"))
        MockClient.return_value = mock_instance

        with pytest.raises(OpenAIOAuthError):
            device_code_start()


# ---------------------------------------------------------------------------
# device_code_poll
# ---------------------------------------------------------------------------


def test_device_code_poll_pending_returns_none():
    with patch("app.oauth.openai_chatgpt.httpx.Client") as MockClient:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post = MagicMock(return_value=httpx.Response(202, json={}))
        MockClient.return_value = mock_instance

        result = device_code_poll("dev_123", "ABCD-1234")

    assert result is None


def test_device_code_poll_authorization_pending_in_body():
    with patch("app.oauth.openai_chatgpt.httpx.Client") as MockClient:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post = MagicMock(
            return_value=httpx.Response(400, text='{"error":"authorization_pending"}')
        )
        MockClient.return_value = mock_instance

        result = device_code_poll("dev_123", "ABCD-1234")

    assert result is None


def test_device_code_poll_complete_returns_bundle():
    payload = {
        "https://api.openai.com/auth": {
            "chatgpt_account_id": "acct_abc",
            "chatgpt_plan_type": "plus",
        }
    }
    access_token = _make_jwt(payload)
    token_response = {
        "access_token": access_token,
        "refresh_token": "refresh_abc",
        "expires_in": 3600,
    }

    # The poll endpoint returns access_token directly (no code exchange).
    with patch("app.oauth.openai_chatgpt.httpx.Client") as MockClient:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post = MagicMock(return_value=httpx.Response(200, json=token_response))
        MockClient.return_value = mock_instance

        result = device_code_poll("dev_123", "ABCD-1234")

    assert result is not None
    assert result.access_token == access_token
    assert result.refresh_token == "refresh_abc"
    assert result.account_id == "acct_abc"
    assert result.plan_type == "plus"


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


def test_refresh_returns_new_expiry():
    payload = {
        "https://api.openai.com/auth": {
            "chatgpt_account_id": "acct_abc",
            "chatgpt_plan_type": "plus",
        }
    }
    new_access = _make_jwt(payload)
    future_ts = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    token_response = {
        "access_token": new_access,
        "refresh_token": "new_refresh",
        "expires_at": future_ts,
    }

    with patch("app.oauth.openai_chatgpt.httpx.Client") as MockClient:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post = MagicMock(return_value=httpx.Response(200, json=token_response))
        MockClient.return_value = mock_instance

        bundle = refresh("old_refresh_token")

    assert bundle.access_token == new_access
    assert bundle.refresh_token == "new_refresh"
    # Expiry should be derived from the upstream expires_at, not now().
    assert abs(bundle.expires_at.timestamp() - future_ts) < 2
