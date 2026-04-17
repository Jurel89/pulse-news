"""Route-level tests for the OAuth OpenAI endpoints.

Uses the existing test infrastructure (in-memory sqlite, authenticated session)
and stubs all upstream OAuth HTTP calls.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

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

    with patch("app.api.oauth_openai.device_code_poll", return_value=None):
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

    with patch("app.api.oauth_openai.device_code_poll", return_value=bundle):
        resp = auth_client.post(
            "/api/oauth/openai/device/poll",
            json={"device_auth_id": "dev_complete"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "complete"
    assert data["api_key_id"] is not None


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

    with patch("app.api.oauth_openai.device_code_poll", return_value=bundle):
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

    with patch("app.api.oauth_openai.device_code_poll", return_value=bundle):
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

    with patch("app.api.oauth_openai.device_code_poll", return_value=bundle):
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
