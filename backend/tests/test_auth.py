from __future__ import annotations

from importlib import reload

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PULSE_NEWS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PULSE_NEWS_SECRET_KEY", "test-secret")
    monkeypatch.setenv("PULSE_NEWS_ENVIRONMENT", "development")

    import app.api.auth
    import app.api.router
    import app.auth
    import app.config
    import app.database
    import app.main
    import app.models
    import app.schemas

    app.config.get_settings.cache_clear()
    app.database.get_engine.cache_clear()
    app.database.get_session_maker.cache_clear()

    reload(app.config)
    reload(app.database)
    reload(app.models)
    reload(app.schemas)
    reload(app.auth)
    reload(app.api.auth)
    reload(app.api.router)
    reload(app.main)
    app.database.init_database()

    with TestClient(app.main.app) as test_client:
        yield test_client


def test_bootstrap_login_and_password_change_flow(client: TestClient):
    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json() == {
        "initialized": False,
        "authenticated": False,
        "user": None,
        "ai_generation_mode": "live",
        "email_delivery_mode": "live",
    }

    health_response = client.get("/api/health")
    assert health_response.status_code == 200
    assert health_response.json()["ai_generation_mode"] == "live"
    assert health_response.json()["email_delivery_mode"] == "live"

    bootstrap_response = client.post(
        "/api/auth/bootstrap",
        json={"email": "operator@example.com", "password": "super-secret-password"},
    )
    assert bootstrap_response.status_code == 201
    bootstrap_payload = bootstrap_response.json()
    assert bootstrap_payload["initialized"] is True
    assert bootstrap_payload["authenticated"] is True
    assert bootstrap_payload["user"]["email"] == "operator@example.com"
    assert bootstrap_payload["ai_generation_mode"] == "live"
    assert bootstrap_payload["email_delivery_mode"] == "live"

    update_settings_response = client.patch(
        "/api/auth/system-settings",
        json={
            "ai_generation_mode": "simulated",
            "email_delivery_mode": "simulated",
        },
    )
    assert update_settings_response.status_code == 200
    assert update_settings_response.json() == {
        "initialized": True,
        "ai_generation_mode": "simulated",
        "email_delivery_mode": "simulated",
    }

    updated_session_response = client.get("/api/auth/session")
    assert updated_session_response.status_code == 200
    assert updated_session_response.json()["ai_generation_mode"] == "simulated"
    assert updated_session_response.json()["email_delivery_mode"] == "simulated"

    updated_health_response = client.get("/api/health")
    assert updated_health_response.status_code == 200
    assert updated_health_response.json()["ai_generation_mode"] == "simulated"
    assert updated_health_response.json()["email_delivery_mode"] == "simulated"

    second_bootstrap_response = client.post(
        "/api/auth/bootstrap",
        json={"email": "other@example.com", "password": "another-secret-password"},
    )
    assert second_bootstrap_response.status_code == 409

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200

    login_response = client.post(
        "/api/auth/login",
        json={"email": "operator@example.com", "password": "super-secret-password"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["authenticated"] is True
    assert login_response.json()["ai_generation_mode"] == "simulated"
    assert login_response.json()["email_delivery_mode"] == "simulated"

    change_password_response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "super-secret-password",
            "new_password": "newer-secret-password",
        },
    )
    assert change_password_response.status_code == 200

    client.post("/api/auth/logout")

    old_password_login = client.post(
        "/api/auth/login",
        json={"email": "operator@example.com", "password": "super-secret-password"},
    )
    assert old_password_login.status_code == 401

    new_password_login = client.post(
        "/api/auth/login",
        json={"email": "operator@example.com", "password": "newer-secret-password"},
    )
    assert new_password_login.status_code == 200
