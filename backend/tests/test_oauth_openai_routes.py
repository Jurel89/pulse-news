"""Route-level tests for the OAuth OpenAI endpoints.

Uses the existing test infrastructure (in-memory sqlite, authenticated session)
and stubs all upstream OAuth HTTP calls.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

CHATGPT_SUBSCRIPTION_MODELS = ["gpt-5.4", "gpt-5.4-mini", "gpt-5.2", "gpt-5.3-codex"]

# ---------------------------------------------------------------------------
# Helpers shared with existing tests
# ---------------------------------------------------------------------------


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("PULSE_NEWS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PULSE_NEWS_SECRET_KEY", "test-secret-key-for-testing-oauth")
    monkeypatch.setenv("PULSE_NEWS_ENVIRONMENT", "development")

    from importlib import reload

    import app.config
    import app.database

    app.config.get_settings.cache_clear()
    app.database.get_engine.cache_clear()
    app.database.get_session_maker.cache_clear()

    reload(app.config)
    reload(app.database)

    app.database.init_database()

    from app.main import app as fastapi_app

    return fastapi_app


def _authenticated_client(app, email="test@example.com", password="password123"):
    from starlette.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=True)
    # Bootstrap
    resp = client.post(
        "/api/auth/bootstrap",
        json={"email": email, "password": password},
    )
    if resp.status_code == 201:
        # Bootstrap succeeded — log in to get a session cookie
        resp = client.post("/api/auth/login", json={"email": email, "password": password})
    elif resp.status_code not in (200,):
        # Already bootstrapped — just log in
        resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


def _make_token_bundle(plan="plus", account_id="acct_test_1234"):
    from app.oauth.openai_chatgpt import TokenBundle

    return TokenBundle(
        access_token="access_tok_test",
        refresh_token="refresh_tok_test",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        account_id=account_id,
        plan_type=plan,
        id_token=None,
    )


def _create_openai_provider(
    auth_client,
    *,
    provider_type: str = "openai",
    default_model: str,
) -> int:
    key_resp = auth_client.post(
        "/api/api-keys",
        json={
            "name": f"{provider_type} key",
            "provider_type": provider_type,
            "key_value": f"sk-test-{provider_type}-key-12345",
            "is_active": True,
        },
    )
    assert key_resp.status_code == 201

    provider_resp = auth_client.post(
        "/api/providers",
        json={
            "name": f"{provider_type} provider",
            "provider_type": provider_type,
            "is_enabled": True,
            "default_model": default_model,
        },
    )
    assert provider_resp.status_code == 201
    return provider_resp.json()["id"]


def _connect_chatgpt_oauth(
    auth_client,
    *,
    device_auth_id: str = "dev_chatgpt_models",
    user_code: str = "CHAT-5555",
    plan: str = "plus",
    account_id: str = "acct_test_1234",
) -> int:
    from app.oauth.openai_chatgpt import DeviceCodeInit

    fake_init = DeviceCodeInit(
        device_auth_id=device_auth_id,
        user_code=user_code,
        interval=5,
        expires_in=900,
        verification_uri="https://auth.openai.com/codex/device",
    )

    with patch("app.api.oauth_openai.device_code_start", return_value=fake_init):
        start_resp = auth_client.post("/api/oauth/openai/device/start")

    assert start_resp.status_code == 201

    bundle = _make_token_bundle(plan=plan, account_id=account_id)

    with patch("app.api.oauth_openai.device_code_poll", return_value=(bundle, None)):
        poll_resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": device_auth_id},
        )

    assert poll_resp.status_code == 200
    assert poll_resp.json()["status"] == "complete"
    return poll_resp.json()["api_key_id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_client(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    return _authenticated_client(app)


def test_device_start_returns_user_code(auth_client):
    from app.oauth.openai_chatgpt import DeviceCodeInit

    fake_init = DeviceCodeInit(
        device_auth_id="dev_123",
        user_code="ABCD-1234",
        interval=5,
        expires_in=900,
        verification_uri="https://auth.openai.com/codex/device",
    )

    with patch("app.api.oauth_openai.device_code_start", return_value=fake_init):
        resp = auth_client.post("/api/oauth/openai/device/start")

    assert resp.status_code == 201
    data = resp.json()
    assert data["device_auth_id"] == "dev_123"
    assert data["user_code"] == "ABCD-1234"
    assert data["verification_uri"] == "https://auth.openai.com/codex/device"


def test_device_poll_pending(auth_client):
    from app.oauth.openai_chatgpt import DeviceCodeInit

    fake_init = DeviceCodeInit(
        device_auth_id="dev_pending",
        user_code="PEND-0000",
        interval=5,
        expires_in=900,
        verification_uri="https://auth.openai.com/codex/device",
    )

    with patch("app.api.oauth_openai.device_code_start", return_value=fake_init):
        auth_client.post("/api/oauth/openai/device/start")

    with patch("app.api.oauth_openai.device_code_poll", return_value=(None, None)):
        resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_pending"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_device_poll_complete_creates_api_key(auth_client):
    from app.oauth.openai_chatgpt import DeviceCodeInit

    fake_init = DeviceCodeInit(
        device_auth_id="dev_complete",
        user_code="COMP-1111",
        interval=5,
        expires_in=900,
        verification_uri="https://auth.openai.com/codex/device",
    )

    with patch("app.api.oauth_openai.device_code_start", return_value=fake_init):
        auth_client.post("/api/oauth/openai/device/start")

    bundle = _make_token_bundle()

    with patch("app.api.oauth_openai.device_code_poll", return_value=(bundle, None)):
        resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_complete"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "complete"
    assert data["api_key_id"] is not None


def test_create_provider_requires_chatgpt_oauth_connection(auth_client):
    response = auth_client.post(
        "/api/providers",
        json={
            "name": "ChatGPT Subscription",
            "provider_type": "openai_chatgpt",
            "is_enabled": True,
            "default_model": "gpt-5.4",
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "OAuth connection" in detail
    assert "API key" not in detail


def test_update_provider_to_chatgpt_requires_oauth_connection(auth_client):
    provider_id = _create_openai_provider(
        auth_client,
        provider_type="openai",
        default_model="gpt-4o-mini",
    )

    response = auth_client.put(
        f"/api/providers/{provider_id}",
        json={
            "name": "ChatGPT Subscription",
            "provider_type": "openai_chatgpt",
            "is_enabled": True,
            "default_model": "gpt-5.4",
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "OAuth connection" in detail
    assert "API key" not in detail


def test_preset_models_skip_oauth_sentinel_validation(auth_client):
    _connect_chatgpt_oauth(auth_client)

    def fail_on_oauth_sentinel(provider_type: str, *, api_key=None, configuration=None):
        assert api_key != "oauth:v1"
        return []

    with (
        patch("app.api.providers.discover_models_for_provider", side_effect=fail_on_oauth_sentinel),
        patch(
            "app.api.providers.validate_provider_model",
            side_effect=AssertionError(
                "ChatGPT OAuth providers should not use LiteLLM verification."
            ),
        ),
    ):
        response = auth_client.get("/api/providers/presets/openai_chatgpt/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["models"] == CHATGPT_SUBSCRIPTION_MODELS
    assert payload["default_model"] == "gpt-5.4"
    assert payload["verified_model"] is None
    assert payload["verification_message"] is None


def test_provider_models_skip_oauth_sentinel_validation(auth_client):
    _connect_chatgpt_oauth(
        auth_client,
        device_auth_id="dev_provider_models",
        user_code="MODL-6666",
    )

    provider_resp = auth_client.post(
        "/api/providers",
        json={
            "name": "ChatGPT Subscription",
            "provider_type": "openai_chatgpt",
            "is_enabled": True,
            "default_model": "gpt-5.4",
        },
    )
    assert provider_resp.status_code == 201
    provider_id = provider_resp.json()["id"]

    def fail_on_oauth_sentinel(provider_type: str, *, api_key=None, configuration=None):
        assert api_key != "oauth:v1"
        return []

    with (
        patch("app.api.providers.discover_models_for_provider", side_effect=fail_on_oauth_sentinel),
        patch(
            "app.api.providers.validate_provider_model",
            side_effect=AssertionError(
                "ChatGPT OAuth providers should not use LiteLLM verification."
            ),
        ),
    ):
        response = auth_client.get(f"/api/providers/{provider_id}/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["models"] == CHATGPT_SUBSCRIPTION_MODELS
    assert payload["default_model"] == "gpt-5.4"
    assert payload["verified_model"] is None
    assert payload["verification_message"] is None


def test_oauth_status_connected(auth_client):
    from app.oauth.openai_chatgpt import DeviceCodeInit

    fake_init = DeviceCodeInit(
        device_auth_id="dev_status",
        user_code="STAT-2222",
        interval=5,
        expires_in=900,
        verification_uri="https://auth.openai.com/codex/device",
    )

    with patch("app.api.oauth_openai.device_code_start", return_value=fake_init):
        auth_client.post("/api/oauth/openai/device/start")

    bundle = _make_token_bundle(plan="pro", account_id="acct_status_test")

    with patch("app.api.oauth_openai.device_code_poll", return_value=(bundle, None)):
        poll_resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_status"},
        )

    api_key_id = poll_resp.json()["api_key_id"]
    resp = auth_client.get(f"/api/oauth/openai/{api_key_id}/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_connected"] is True
    assert data["plan_type"] == "pro"
    assert data["account_id"] == "acct_status_test"
    assert data["expires_in_seconds"] is not None and data["expires_in_seconds"] > 0


def test_oauth_refresh_updates_token(auth_client):
    from app.oauth.openai_chatgpt import DeviceCodeInit, TokenBundle

    fake_init = DeviceCodeInit(
        device_auth_id="dev_refresh",
        user_code="REFR-3333",
        interval=5,
        expires_in=900,
        verification_uri="https://auth.openai.com/codex/device",
    )

    with patch("app.api.oauth_openai.device_code_start", return_value=fake_init):
        auth_client.post("/api/oauth/openai/device/start")

    bundle = _make_token_bundle()

    with patch("app.api.oauth_openai.device_code_poll", return_value=(bundle, None)):
        poll_resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_refresh"},
        )

    api_key_id = poll_resp.json()["api_key_id"]

    new_bundle = TokenBundle(
        access_token="new_access_token",
        refresh_token="new_refresh_token",
        expires_at=datetime.now(UTC) + timedelta(hours=2),
        account_id="acct_test_1234",
        plan_type="plus",
        id_token=None,
    )

    with patch("app.api.oauth_openai.oauth_refresh", return_value=new_bundle):
        resp = auth_client.post(f"/api/oauth/openai/refresh/{api_key_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["expires_in_seconds"] > 3600


def test_device_code_poll_403_authorization_unknown_is_pending():
    """OpenAI returns 403 deviceauth_authorization_unknown while the user
    has not yet authorised the device.

    This must be treated as a retryable pending state, not a fatal error.
    """
    from unittest.mock import MagicMock, patch

    from app.oauth.openai_chatgpt import device_code_poll

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = '{"error":"deviceauth_authorization_unknown"}'
    mock_response.json.return_value = {"error": "deviceauth_authorization_unknown"}

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.oauth.openai_chatgpt.httpx.Client", return_value=mock_client):
        result = device_code_poll("dev_auth_123", "USER-CODE")

    assert result == (None, None)


def test_device_code_poll_403_other_is_fatal():
    """A 403 with any other error code must still be treated as fatal."""
    from unittest.mock import MagicMock, patch

    from app.oauth.openai_chatgpt import OpenAIOAuthError, device_code_poll

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = '{"error":"access_denied"}'

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.oauth.openai_chatgpt.httpx.Client", return_value=mock_client):
        with pytest.raises(OpenAIOAuthError) as exc_info:
            device_code_poll("dev_auth_123", "USER-CODE")

    assert exc_info.value.status_code == 403


def test_device_code_poll_404_authorization_unknown_is_pending():
    """OpenAI can return 404 deviceauth_authorization_unknown while the user
    has not yet authorised the device.

    This must also be treated as a retryable pending state.
    """
    from unittest.mock import MagicMock, patch

    from app.oauth.openai_chatgpt import device_code_poll

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = '{"error":"deviceauth_authorization_unknown"}'
    mock_response.json.return_value = {"error": "deviceauth_authorization_unknown"}

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.oauth.openai_chatgpt.httpx.Client", return_value=mock_client):
        result = device_code_poll("dev_auth_123", "USER-CODE")

    assert result == (None, None)


def test_device_code_poll_slow_down_is_pending():
    """RFC 8628 slow_down must be treated as retryable pending."""
    from unittest.mock import MagicMock, patch

    from app.oauth.openai_chatgpt import device_code_poll

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"error":"slow_down","interval":10}'
    mock_response.json.return_value = {"error": "slow_down", "interval": 10}

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.oauth.openai_chatgpt.httpx.Client", return_value=mock_client):
        result = device_code_poll("dev_auth_123", "USER-CODE")

    assert result[0] is None
    assert result[1] == 10


def test_device_code_poll_nested_error_is_pending():
    """OpenAI sometimes returns nested error.code shapes that must be retryable."""
    from unittest.mock import MagicMock, patch

    from app.oauth.openai_chatgpt import device_code_poll

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = '{"error":{"code":"deviceauth_authorization_unknown"}}'
    mock_response.json.return_value = {"error": {"code": "deviceauth_authorization_unknown"}}

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.oauth.openai_chatgpt.httpx.Client", return_value=mock_client):
        result = device_code_poll("dev_auth_123", "USER-CODE")

    assert result[0] is None


def test_device_code_poll_message_only_is_pending():
    """OpenAI sometimes returns a plain-text message instead of structured error."""
    from unittest.mock import MagicMock, patch

    from app.oauth.openai_chatgpt import device_code_poll

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = '"Device authorization is unknown"'
    mock_response.json.return_value = "Device authorization is unknown"

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.oauth.openai_chatgpt.httpx.Client", return_value=mock_client):
        result = device_code_poll("dev_auth_123", "USER-CODE")

    assert result[0] is None


def test_device_code_poll_network_error_is_oauth_error():
    """Network / timeout failures must be wrapped in OpenAIOAuthError."""
    from unittest.mock import MagicMock, patch

    import httpx
    import pytest

    from app.oauth.openai_chatgpt import OpenAIOAuthError, device_code_poll

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.side_effect = httpx.ConnectTimeout("Connection timed out")

    with patch("app.oauth.openai_chatgpt.httpx.Client", return_value=mock_client):
        with pytest.raises(OpenAIOAuthError) as exc_info:
            device_code_poll("dev_auth_123", "USER-CODE")

    assert "network error" in str(exc_info.value).lower()
    assert exc_info.value.status_code is None


def test_oauth_delete_removes_connection(auth_client):
    from app.oauth.openai_chatgpt import DeviceCodeInit

    fake_init = DeviceCodeInit(
        device_auth_id="dev_delete",
        user_code="DELT-4444",
        interval=5,
        expires_in=900,
        verification_uri="https://auth.openai.com/codex/device",
    )

    with patch("app.api.oauth_openai.device_code_start", return_value=fake_init):
        auth_client.post("/api/oauth/openai/device/start")

    bundle = _make_token_bundle()

    with patch("app.api.oauth_openai.device_code_poll", return_value=(bundle, None)):
        poll_resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_delete"},
        )

    api_key_id = poll_resp.json()["api_key_id"]

    resp = auth_client.delete(f"/api/oauth/openai/{api_key_id}")
    assert resp.status_code == 204

    # Confirm it's gone
    status_resp = auth_client.get(f"/api/oauth/openai/{api_key_id}/status")
    assert status_resp.status_code == 404


def test_oauth_delete_blocks_last_connection_when_provider_enabled(auth_client):
    """Deleting the only active OAuth connection must fail when a provider depends on it."""
    from app.models import Provider
    from app.oauth.openai_chatgpt import DeviceCodeInit

    fake_init = DeviceCodeInit(
        device_auth_id="dev_conflict",
        user_code="CONF-1234",
        interval=5,
        expires_in=900,
        verification_uri="https://auth.openai.com/codex/device",
    )

    with patch("app.api.oauth_openai.device_code_start", return_value=fake_init):
        auth_client.post("/api/oauth/openai/device/start")

    bundle = _make_token_bundle()

    with patch("app.api.oauth_openai.device_code_poll", return_value=(bundle, None)):
        poll_resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_conflict"},
        )

    api_key_id = poll_resp.json()["api_key_id"]

    # Create an enabled ChatGPT provider that depends on this connection
    provider = Provider(
        name="ChatGPT Provider",
        provider_type="openai_chatgpt",
        is_enabled=True,
        default_model="gpt-5.4",
    )
    db = auth_client.app.state._db_session_factory()
    db.add(provider)
    db.commit()
    db.close()

    resp = auth_client.delete(f"/api/oauth/openai/{api_key_id}")
    assert resp.status_code == 409
    assert "Cannot disconnect" in resp.text


def test_device_poll_returns_502_on_network_error(auth_client):
    """A network failure during poll must return 502 and preserve the session."""
    from app.oauth.openai_chatgpt import DeviceCodeInit, OpenAIOAuthError

    fake_init = DeviceCodeInit(
        device_auth_id="dev_net",
        user_code="NETW-1234",
        interval=5,
        expires_in=900,
        verification_uri="https://auth.openai.com/codex/device",
    )

    with patch("app.api.oauth_openai.device_code_start", return_value=fake_init):
        auth_client.post("/api/oauth/openai/device/start")

    with patch(
        "app.api.oauth_openai.device_code_poll",
        side_effect=OpenAIOAuthError("Connection timed out"),
    ):
        poll_resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_net"},
        )

    assert poll_resp.status_code == 502
    detail = poll_resp.json()["detail"]
    assert "Connection timed out" in detail

    # Session must still be valid so the client can retry.
    with patch(
        "app.api.oauth_openai.device_code_poll",
        side_effect=OpenAIOAuthError("Connection timed out"),
    ):
        retry_resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_net"},
        )
    assert retry_resp.status_code == 502


def test_device_poll_returns_502_on_upstream_502_error(auth_client):
    """An upstream 502 from OpenAI must be treated as transient (session kept)."""
    from app.oauth.openai_chatgpt import DeviceCodeInit, OpenAIOAuthError

    fake_init = DeviceCodeInit(
        device_auth_id="dev_502",
        user_code="FIFT-1234",
        interval=5,
        expires_in=900,
        verification_uri="https://auth.openai.com/codex/device",
    )

    with patch("app.api.oauth_openai.device_code_start", return_value=fake_init):
        auth_client.post("/api/oauth/openai/device/start")

    with patch(
        "app.api.oauth_openai.device_code_poll",
        side_effect=OpenAIOAuthError("Upstream unavailable", status_code=502),
    ):
        poll_resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_502"},
        )

    assert poll_resp.status_code == 502
    detail = poll_resp.json()["detail"]
    assert "Upstream unavailable" in detail

    # Session must still be valid so the client can retry.
    with patch(
        "app.api.oauth_openai.device_code_poll",
        side_effect=OpenAIOAuthError("Upstream unavailable", status_code=502),
    ):
        retry_resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_502"},
        )
    assert retry_resp.status_code == 502


def test_device_poll_returns_400_on_hard_auth_failure(auth_client):
    """A hard auth failure during poll must return 400 and clear the session."""
    from app.oauth.openai_chatgpt import DeviceCodeInit, OpenAIOAuthError

    fake_init = DeviceCodeInit(
        device_auth_id="dev_hard",
        user_code="HARD-1234",
        interval=5,
        expires_in=900,
        verification_uri="https://auth.openai.com/codex/device",
    )

    with patch("app.api.oauth_openai.device_code_start", return_value=fake_init):
        auth_client.post("/api/oauth/openai/device/start")

    with patch(
        "app.api.oauth_openai.device_code_poll",
        side_effect=OpenAIOAuthError("Access denied", status_code=400),
    ):
        poll_resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_hard"},
        )

    assert poll_resp.status_code == 400
    detail = poll_resp.json()["detail"]
    assert "Access denied" in detail

    # Session must be cleared so retrying the same id fails.
    retry_resp = auth_client.post(
        "/api/oauth/openai/device/poll",
        json={"device_auth_id": "dev_hard"},
    )
    assert retry_resp.status_code == 404


def test_provider_test_rejects_expired_oauth_token(auth_client):
    """Test Connection for ChatGPT must fail when the OAuth token is expired."""
    from datetime import UTC
    from datetime import datetime as _dt

    from app.crypto import encrypt_secret
    from app.database import get_session_maker
    from app.models import ApiKey, Provider

    session = get_session_maker()()
    provider = Provider(
        name="ChatGPT Subscription",
        provider_type="openai_chatgpt",
        is_enabled=True,
        default_model="gpt-5.4",
    )
    session.add(provider)
    session.commit()
    session.refresh(provider)
    provider_id = provider.id

    expired_key = ApiKey(
        name="ChatGPT Plus",
        provider_type="openai_chatgpt",
        auth_type="oauth",
        key_value=encrypt_secret("oauth:v1"),
        oauth_access_token=encrypt_secret("valid_token"),
        oauth_refresh_token=encrypt_secret("valid_refresh"),
        oauth_expires_at=_dt.now(UTC) - timedelta(hours=1),
        is_active=True,
    )
    session.add(expired_key)
    session.commit()
    session.close()

    resp = auth_client.post(f"/api/providers/{provider_id}/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "warning"
    assert "expired" in data["message"].lower() or "invalid" in data["message"].lower()
