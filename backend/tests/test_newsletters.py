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
    import app.api.public
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
    reload(app.api.public)
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

    preview_response = client.get(f"/api/newsletters/{created_newsletter['id']}/preview")
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["subject"] == "Daily Brief Europe"
    assert "Updated copy block" in preview_payload["plain_text"]
    assert "Daily Brief Europe" in preview_payload["html"]
    assert preview_payload["template_key"] == "ledger"

    test_send_response = client.post(
        f"/api/newsletters/{created_newsletter['id']}/test-send",
        json={"to_email": "qa@example.com"},
    )
    assert test_send_response.status_code == 200
    assert test_send_response.json()["mode"] == "local-preview"
    assert test_send_response.json()["to_email"] == "qa@example.com"

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


def test_generate_draft_flow_uses_normalized_result_shape(client: TestClient):
    bootstrap_operator(client)

    create_response = client.post(
        "/api/newsletters",
        json={
            "name": "Founder Radar",
            "description": "Signals for startup operators",
            "prompt": (
                "Summarize the top startup infrastructure news "
                "for founders in a concise tone."
            ),
            "draft_subject": "",
            "draft_preheader": "",
            "draft_body_text": "",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "founders",
            "timezone": "UTC",
            "schedule_cron": None,
            "status": "draft",
            "notes": "Used for generation tests",
            "recipient_import_text": "founder@example.com"
        },
    )
    assert create_response.status_code == 201
    newsletter_id = create_response.json()["id"]

    generate_response = client.post(f"/api/newsletters/{newsletter_id}/generate-draft")
    assert generate_response.status_code == 200

    payload = generate_response.json()
    assert payload["status"] in {"generated", "fallback"}
    assert payload["message"]
    assert payload["newsletter"]["id"] == newsletter_id
    assert payload["newsletter"]["draft_subject"]
    assert payload["newsletter"]["draft_body_text"]
    assert payload["run"]["newsletter_id"] == newsletter_id
    assert payload["run"]["trigger_mode"] == "manual-generate"
    assert payload["run"]["provider_name"] == "openai"
    assert payload["run"]["recipient_count"] == 1
    assert payload["run"]["snapshot_subject"] == payload["newsletter"]["draft_subject"]

    send_response = client.post(f"/api/newsletters/{newsletter_id}/send")
    assert send_response.status_code == 200

    send_payload = send_response.json()
    assert send_payload["status"] in {"sent", "fallback"}
    assert send_payload["run"]["newsletter_id"] == newsletter_id
    assert send_payload["run"]["trigger_mode"] == "manual-send"
    assert send_payload["run"]["recipient_count"] == 1
    assert send_payload["recipient_outcomes"][0]["email"] == "founder@example.com"


def test_unsubscribe_suppresses_future_manual_sends(client: TestClient):
    bootstrap_operator(client)

    create_response = client.post(
        "/api/newsletters",
        json={
            "name": "Compliance Brief",
            "description": "Compliance workflow test",
            "prompt": "Generate compliance newsletter content.",
            "draft_subject": "Compliance Brief",
            "draft_preheader": "Suppression workflow",
            "draft_body_text": "Delivery topic test body",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "ops",
            "timezone": "UTC",
            "schedule_cron": None,
            "schedule_enabled": False,
            "status": "active",
            "notes": "Used for unsubscribe tests",
            "recipient_import_text": "first@example.com\nsecond@example.com",
            "delivery_topic": "ops-compliance"
        },
    )
    assert create_response.status_code == 201
    newsletter = create_response.json()

    token = newsletter["recipients"][0]["unsubscribe_token"]
    unsubscribe_response = client.post(f"/api/public/unsubscribe/{token}")
    assert unsubscribe_response.status_code == 200

    send_response = client.post(f"/api/newsletters/{newsletter['id']}/send")
    assert send_response.status_code == 200
    send_payload = send_response.json()
    assert send_payload["run"]["recipient_count"] == 1
    assert send_payload["recipient_outcomes"][0]["email"] == "second@example.com"
