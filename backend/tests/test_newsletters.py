from __future__ import annotations

from importlib import reload

import pytest
from fastapi.testclient import TestClient


def create_test_api_key(client: TestClient, provider_type: str = "openai") -> int:
    response = client.post(
        "/api/api-keys",
        json={
            "name": f"Test {provider_type} Key",
            "provider_type": provider_type,
            "key_value": f"sk-test-{provider_type}-key-12345",
            "is_active": True,
        },
    )
    assert response.status_code == 201, f"Failed to create API key: {response.text}"
    return response.json()["id"]


def create_test_provider(
    client: TestClient, provider_type: str = "openai", is_enabled: bool = True
) -> int:
    create_test_api_key(client, provider_type)

    response = client.post(
        "/api/providers",
        json={
            "name": f"Test {provider_type.title()}",
            "provider_type": provider_type,
            "is_enabled": is_enabled,
            "default_model": "gpt-4o-mini",
        },
    )
    assert response.status_code == 201, f"Failed to create provider: {response.text}"
    return response.json()["id"]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PULSE_NEWS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PULSE_NEWS_SECRET_KEY", "test-secret")
    monkeypatch.setenv("PULSE_NEWS_ENVIRONMENT", "development")

    import app.api.auth
    import app.api.newsletters
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
    reload(app.api.newsletters)
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

    create_test_provider(client, "openai")

    create_response = client.post(
        "/api/newsletters",
        json={
            "name": "Daily Brief",
            "description": "Morning AI news digest",
            "prompt": "Summarize the top AI infrastructure news for founders.",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "founders",
            "delivery_topic": "daily-brief",
            "timezone": "Europe/Madrid",
            "schedule_enabled": False,
            "schedule_cron": "0 7 * * 1-5",
            "status": "active",
            "notes": "Primary weekday newsletter",
            "recipient_import_text": "ceo@example.com\nops@example.com,founder@example.com",
        },
    )
    assert create_response.status_code == 201
    created_newsletter = create_response.json()
    assert created_newsletter["slug"] == "daily-brief"
    assert created_newsletter["status"] == "active"
    assert len(created_newsletter["recipients"]) == 3
    assert created_newsletter["subject"] == ""

    list_response = client.get("/api/newsletters")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    create_test_provider(client, "anthropic")

    update_response = client.put(
        f"/api/newsletters/{created_newsletter['id']}",
        json={
            "name": "Daily Brief Europe",
            "description": "Morning AI news digest for Europe",
            "prompt": "Summarize the top AI infrastructure news for European operators.",
            "provider_name": "anthropic",
            "model_name": "claude-3-5-sonnet-latest",
            "template_key": "ledger",
            "audience_name": "europe-operators",
            "delivery_topic": "daily-brief-europe",
            "timezone": "Europe/Madrid",
            "schedule_enabled": True,
            "schedule_cron": "0 6 * * 1-5",
            "status": "active",
            "notes": "Updated notes",
            "recipient_import_text": "ceo@example.com\nfounder@example.com",
        },
    )
    assert update_response.status_code == 200
    updated_newsletter = update_response.json()
    assert updated_newsletter["name"] == "Daily Brief Europe"
    assert updated_newsletter["slug"] == "daily-brief-europe"
    assert updated_newsletter["schedule_enabled"] is True
    assert len(updated_newsletter["recipients"]) == 2

    get_response = client.get(f"/api/newsletters/{created_newsletter['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Daily Brief Europe"

    delete_response = client.delete(f"/api/newsletters/{created_newsletter['id']}")
    assert delete_response.status_code == 204

    list_after_delete = client.get("/api/newsletters")
    assert list_after_delete.status_code == 200
    assert len(list_after_delete.json()) == 0


def test_generate_content_and_run_flow(client: TestClient, monkeypatch):
    import app.ai_generation
    import app.email_delivery

    bootstrap_operator(client)

    create_test_provider(client, "openai")

    create_response = client.post(
        "/api/newsletters",
        json={
            "name": "Draft Test",
            "description": "Testing draft generation",
            "prompt": "Write a brief about testing using https://example.com/source.",
            "subject": "Draft Test Subject",
            "preheader": "Draft preheader",
            "body_text": "Initial body",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "testers",
            "delivery_topic": "draft-test",
            "timezone": "UTC",
            "schedule_enabled": False,
            "status": "active",
            "recipient_import_text": "test@example.com",
        },
    )
    assert create_response.status_code == 201
    newsletter_id = create_response.json()["id"]

    import app.ai_generation

    monkeypatch.setattr(
        "app.api.newsletters.generate_newsletter_content",
        lambda newsletter, db_session=None: app.ai_generation.GeneratedContent(
            status="generated",
            mode="litellm",
            message="Generated content successfully.",
            subject="Generated Subject",
            preheader="Generated preheader",
            body_text="Generated body content",
            provider_snapshot_json="{}",
        ),
    )

    class FakeResponse:
        def read(self):
            return b'{"id":"resend-msg-id"}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("app.email_delivery.request.urlopen", lambda req, timeout: FakeResponse())
    monkeypatch.setenv("PULSE_NEWS_RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("PULSE_NEWS_RESEND_FROM_EMAIL", "newsletter@example.com")
    app.config.get_settings.cache_clear()

    run_response = client.post(f"/api/newsletters/{newsletter_id}/run")
    assert run_response.status_code == 200
    result = run_response.json()

    assert "status" in result
    assert "mode" in result
    assert "message" in result
    assert "run" in result
    assert "recipient_outcomes" in result
    assert result["status"] == "sent"
    assert result["run"]["newsletter_id"] == newsletter_id
    assert result["run"]["run_type"] == "delivery"
    assert result["run"]["trigger_mode"] == "manual-run"
    assert len(result["recipient_outcomes"]) == 1
    assert result["recipient_outcomes"][0]["email"] == "test@example.com"

    get_response = client.get(f"/api/newsletters/{newsletter_id}")
    assert get_response.status_code == 200
    fetched_newsletter = get_response.json()
    assert fetched_newsletter["id"] == newsletter_id
    assert fetched_newsletter["subject"] == "Generated Subject"
    assert fetched_newsletter["preheader"] == "Generated preheader"
    assert fetched_newsletter["body_text"] == "Generated body content"
    assert fetched_newsletter["recipients"][0]["email"] == "test@example.com"


def test_run_hard_stops_when_generation_fails(client: TestClient, monkeypatch):
    import app.ai_generation
    import app.email_delivery

    bootstrap_operator(client)
    create_test_provider(client, "openai")

    create_response = client.post(
        "/api/newsletters",
        json={
            "name": "Fail Test",
            "description": "Testing generation failure hard stop",
            "prompt": "Write a brief that will fail.",
            "subject": "Fail Test Subject",
            "preheader": "Fail preheader",
            "body_text": "Initial body",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "testers",
            "delivery_topic": "fail-test",
            "timezone": "UTC",
            "schedule_enabled": False,
            "status": "active",
            "recipient_import_text": "test@example.com",
        },
    )
    assert create_response.status_code == 201
    newsletter_id = create_response.json()["id"]

    urlopen_calls = []
    original_urlopen = app.email_delivery.request.urlopen

    def tracking_urlopen(req, timeout=None):
        urlopen_calls.append(req)
        return original_urlopen(req, timeout)

    monkeypatch.setattr(
        "app.api.newsletters.generate_newsletter_content",
        lambda newsletter, db_session=None: app.ai_generation.GeneratedContent(
            status="error",
            mode="none",
            message="Provider rejected the request.",
            subject="",
            preheader="",
            body_text="",
            provider_snapshot_json="{}",
        ),
    )
    monkeypatch.setattr(app.email_delivery.request, "urlopen", tracking_urlopen)

    run_response = client.post(f"/api/newsletters/{newsletter_id}/run")
    assert run_response.status_code == 422
    assert "Generation failed" in run_response.json()["detail"]
    assert len(urlopen_calls) == 0

    # Generation failures must be visible in the operational logs so operators
    # aren't blind when the AI step breaks.
    runs_response = client.get(f"/api/runs?newsletter_id={newsletter_id}")
    assert runs_response.status_code == 200
    runs = runs_response.json()["items"]
    failed_generation_runs = [
        r for r in runs if r["run_type"] == "generation" and r["run_status"] == "failed"
    ]
    assert len(failed_generation_runs) == 1
    assert "Provider rejected the request." in (failed_generation_runs[0]["failure_reason"] or "")

    events_response = client.get(
        f"/api/runs/events?newsletter_id={newsletter_id}&event_type=generation"
    )
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert any(e["status"] == "failed" for e in events)


def test_newsletter_validation_requires_chatgpt_oauth_connection(client: TestClient):
    from app.database import get_session_maker
    from app.models import Provider

    bootstrap_operator(client)

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
    session.close()

    response = client.post(
        "/api/newsletters",
        json={
            "name": "ChatGPT Newsletter",
            "description": "Needs an OAuth-backed provider",
            "prompt": "Summarize the top AI product launches this week.",
            "provider_id": provider_id,
            "provider_name": "openai_chatgpt",
            "model_name": "gpt-5.4",
            "template_key": "signal",
            "audience_name": "operators",
            "delivery_topic": "chatgpt-newsletter",
            "timezone": "UTC",
            "schedule_enabled": False,
            "status": "active",
            "recipient_import_text": "reader@example.com",
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "OAuth connection" in detail
    assert "API key" not in detail


def test_schedule_pause_and_resume_flow(client: TestClient):
    bootstrap_operator(client)
    create_test_provider(client, "openai")

    create_response = client.post(
        "/api/newsletters",
        json={
            "name": "Scheduled Brief",
            "description": "Scheduled delivery test",
            "prompt": "Write a brief about schedules.",
            "subject": "Scheduled Brief",
            "preheader": "Schedule test preheader",
            "body_text": "Schedule test body",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "operators",
            "delivery_topic": "scheduled-brief",
            "timezone": "UTC",
            "schedule_enabled": True,
            "schedule_cron": "0 7 * * 1-5",
            "status": "active",
            "recipient_import_text": "schedule@example.com",
        },
    )
    assert create_response.status_code == 201
    newsletter_id = create_response.json()["id"]

    pause_response = client.post(f"/api/newsletters/{newsletter_id}/schedule/pause")
    assert pause_response.status_code == 200
    paused_newsletter = pause_response.json()
    assert paused_newsletter["schedule_enabled"] is False
    assert paused_newsletter["status"] == "active"

    resume_response = client.post(f"/api/newsletters/{newsletter_id}/schedule/resume")
    assert resume_response.status_code == 200
    resumed_newsletter = resume_response.json()
    assert resumed_newsletter["schedule_enabled"] is True
    assert resumed_newsletter["schedule_cron"] == "0 7 * * 1-5"
    assert resumed_newsletter["status"] == "active"


def test_archive_newsletter_disables_schedule(client: TestClient):
    bootstrap_operator(client)
    create_test_provider(client, "openai")

    create_response = client.post(
        "/api/newsletters",
        json={
            "name": "Archive Brief",
            "description": "Archive flow test",
            "prompt": "Write a brief about archives.",
            "subject": "Archive Brief",
            "preheader": "Archive preheader",
            "body_text": "Archive body",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "operators",
            "delivery_topic": "archive-brief",
            "timezone": "UTC",
            "schedule_enabled": True,
            "schedule_cron": "0 8 * * 1-5",
            "status": "active",
            "recipient_import_text": "archive@example.com",
        },
    )
    assert create_response.status_code == 201
    newsletter_id = create_response.json()["id"]

    archive_response = client.post(f"/api/newsletters/{newsletter_id}/archive")
    assert archive_response.status_code == 200
    archived_newsletter = archive_response.json()
    assert archived_newsletter["status"] == "archived"
    assert archived_newsletter["schedule_enabled"] is False

    get_response = client.get(f"/api/newsletters/{newsletter_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "archived"


def test_unsubscribe_suppresses_future_manual_sends(client: TestClient):
    bootstrap_operator(client)

    create_test_provider(client, "openai")

    create_response = client.post(
        "/api/newsletters",
        json={
            "name": "Unsubscribe Test",
            "description": "Testing unsubscribe suppression",
            "prompt": "Write a brief.",
            "subject": "Unsubscribe Test",
            "preheader": "Test preheader",
            "body_text": "Test body",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "testers",
            "delivery_topic": "unsubscribe-test",
            "timezone": "UTC",
            "schedule_enabled": False,
            "status": "active",
            "recipient_import_text": "recipient@example.com",
        },
    )
    assert create_response.status_code == 201
    newsletter_id = create_response.json()["id"]
    recipient_token = create_response.json()["recipients"][0]["unsubscribe_token"]

    unsubscribe_response = client.post(
        f"/api/public/unsubscribe/{recipient_token}", follow_redirects=False
    )
    assert unsubscribe_response.status_code == 200

    get_response = client.get(f"/api/newsletters/{newsletter_id}")
    assert get_response.status_code == 200
    recipients = get_response.json()["recipients"]
    assert len(recipients) == 0
