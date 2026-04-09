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


def bootstrap_operator(client: TestClient) -> None:
    response = client.post(
        "/api/auth/bootstrap",
        json={"email": "operator@example.com", "password": "super-secret-password"},
    )
    assert response.status_code == 201


def test_newsletter_crud_flow(client: TestClient):
    bootstrap_operator(client)

    create_response = client.post(
        "/api/newsletters",
        json={
            "name": "Daily Brief",
            "description": "Morning AI news digest",
            "prompt": "Summarize the top AI infrastructure news for founders.",
            "draft_subject": "Daily Brief: AI infrastructure headlines",
            "draft_preheader": "Five stories to scan before breakfast",
            "draft_body_text": "Story one\n\nStory two\n\nStory three",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "founders",
            "timezone": "Europe/Madrid",
            "schedule_cron": "0 7 * * 1-5",
            "status": "active",
            "notes": "Primary weekday newsletter",
            "recipient_import_text": "ceo@example.com\nops@example.com,founder@example.com"
        },
    )
    assert create_response.status_code == 201
    created_newsletter = create_response.json()
    assert created_newsletter["slug"] == "daily-brief"
    assert created_newsletter["status"] == "active"
    assert len(created_newsletter["recipients"]) == 3
    assert created_newsletter["draft_subject"] == "Daily Brief: AI infrastructure headlines"

    list_response = client.get("/api/newsletters")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.put(
        f"/api/newsletters/{created_newsletter['id']}",
        json={
            "name": "Daily Brief Europe",
            "description": "Morning AI news digest for Europe",
            "prompt": "Summarize the top AI infrastructure news for European operators.",
            "draft_subject": "Daily Brief Europe",
            "draft_preheader": "European operator scan",
            "draft_body_text": "Updated copy block",
            "provider_name": "anthropic",
            "model_name": "claude-sonnet-4-20250514",
            "template_key": "ledger",
            "audience_name": "europe-operators",
            "timezone": "Europe/Madrid",
            "schedule_cron": "15 7 * * 1-5",
            "status": "draft",
            "notes": "Renamed for regional edition",
            "recipient_import_text": "europe@example.com"
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["slug"] == "daily-brief-europe"
    assert update_response.json()["provider_name"] == "anthropic"
    assert update_response.json()["recipient_import_text"] == "europe@example.com"
    assert len(update_response.json()["recipients"]) == 1

    pause_response = client.post(f"/api/newsletters/{created_newsletter['id']}/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"

    archive_response = client.post(f"/api/newsletters/{created_newsletter['id']}/archive")
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    delete_response = client.delete(f"/api/newsletters/{created_newsletter['id']}")
    assert delete_response.status_code == 204

    final_list_response = client.get("/api/newsletters")
    assert final_list_response.status_code == 200
    assert final_list_response.json() == []
