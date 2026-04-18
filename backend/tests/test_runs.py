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


def create_newsletter(client: TestClient) -> dict:
    create_test_provider(client, "openai")

    response = client.post(
        "/api/newsletters",
        json={
            "name": "Scheduler Brief",
            "description": "Recurring scheduling test",
            "prompt": "Generate a recurring operations newsletter.",
            "subject": "Scheduler Brief",
            "preheader": "Recurring operations pulse",
            "body_text": "Recurring story block",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "ops",
            "delivery_topic": "scheduler-brief",
            "timezone": "UTC",
            "schedule_enabled": False,
            "schedule_cron": "0 7 * * 1-5",
            "status": "active",
            "notes": "Used for scheduler tests",
            "recipient_import_text": "ops@example.com",
        },
    )
    assert response.status_code == 201
    return response.json()


def _stub_generation_and_delivery(monkeypatch) -> None:
    import app.ai_generation
    import app.config

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


def test_schedule_controls_enable_and_disable_newsletter_schedule(client: TestClient):
    bootstrap_operator(client)
    newsletter = create_newsletter(client)

    resume_response = client.post(f"/api/newsletters/{newsletter['id']}/schedule/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["schedule_enabled"] is True

    pause_response = client.post(f"/api/newsletters/{newsletter['id']}/schedule/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["schedule_enabled"] is False


def test_run_dashboard_filters_and_details(client: TestClient, monkeypatch):
    bootstrap_operator(client)
    newsletter = create_newsletter(client)
    _stub_generation_and_delivery(monkeypatch)

    run_response = client.post(f"/api/newsletters/{newsletter['id']}/run")
    assert run_response.status_code == 200
    run_id = run_response.json()["run"]["id"]

    runs_response = client.get(
        "/api/runs",
        params={"newsletter_id": newsletter["id"], "trigger_mode": "manual-run"},
    )
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["items"]
    assert all(item["trigger_mode"] == "manual-run" for item in runs_payload["items"])

    run_detail_response = client.get(f"/api/runs/{run_id}")
    assert run_detail_response.status_code == 200
    detail_payload = run_detail_response.json()
    assert detail_payload["run"]["id"] == run_id
    assert detail_payload["run"]["snapshot_subject"]
    assert detail_payload["recipient_outcomes"]

    refreshed_detail = client.get(f"/api/runs/{run_id}")
    assert refreshed_detail.status_code == 200
    assert refreshed_detail.json()["events"]


def test_manual_run_always_creates_new_run(client: TestClient, monkeypatch):
    bootstrap_operator(client)
    newsletter = create_newsletter(client)
    _stub_generation_and_delivery(monkeypatch)

    first_run_response = client.post(f"/api/newsletters/{newsletter['id']}/run")
    assert first_run_response.status_code == 200
    first_run = first_run_response.json()["run"]

    second_run_response = client.post(f"/api/newsletters/{newsletter['id']}/run")
    assert second_run_response.status_code == 200
    second_run = second_run_response.json()["run"]

    assert second_run["id"] != first_run["id"]


def test_duplicate_scheduled_send_uses_fire_scope(client: TestClient):
    import app.database
    from app.api.newsletters import execute_newsletter_send
    from app.models import Newsletter

    bootstrap_operator(client)
    newsletter_payload = create_newsletter(client)

    session = app.database.get_session_maker()()
    try:
        newsletter = session.get(Newsletter, newsletter_payload["id"])
        assert newsletter is not None
        newsletter.body_text = "Test body content"
        session.add(newsletter)
        session.commit()
        session.refresh(newsletter)
        first_response, first_run = execute_newsletter_send(
            session,
            newsletter,
            trigger_mode="scheduled-send",
            fire_scope="2026-04-13T10:00:00+00:00",
        )
        second_response, second_run = execute_newsletter_send(
            session,
            newsletter,
            trigger_mode="scheduled-send",
            fire_scope="2026-04-20T10:00:00+00:00",
        )
        assert first_response.run.id != second_response.run.id
        assert first_run.attempt_key != second_run.attempt_key
    finally:
        session.close()


def test_operational_events_endpoint_excludes_runs_by_default(client: TestClient, monkeypatch):
    """Default (include_runs omitted / false) must return only run_event rows."""
    bootstrap_operator(client)
    newsletter = create_newsletter(client)
    _stub_generation_and_delivery(monkeypatch)

    run_response = client.post(f"/api/newsletters/{newsletter['id']}/run")
    assert run_response.status_code == 200

    # Default — include_runs not passed, so False
    events_response = client.get(
        "/api/runs/events",
        params={"search": newsletter["name"]},
    )
    assert events_response.status_code == 200
    items = events_response.json()["items"]
    assert items, "Expected run_event rows even with default include_runs=false"
    assert all(
        item["source"] == "run_event" for item in items
    ), "Default response must only include run_event-source entries"

    # Explicit ?include_runs=false also returns only run_event rows
    explicit_false_response = client.get(
        "/api/runs/events",
        params={"search": newsletter["name"], "include_runs": "false"},
    )
    assert explicit_false_response.status_code == 200
    explicit_items = explicit_false_response.json()["items"]
    assert all(item["source"] == "run_event" for item in explicit_items)

    # event_type filter still works
    delivery_events_response = client.get(
        "/api/runs/events",
        params={"event_type": "delivery"},
    )
    assert delivery_events_response.status_code == 200
    delivery_items = delivery_events_response.json()["items"]
    assert delivery_items
    assert all(item["source"] == "run_event" for item in delivery_items)
    assert all(item["event_type"] == "delivery" for item in delivery_items)

    # status filter still works
    status_events_response = client.get(
        "/api/runs/events",
        params={"status": "sent"},
    )
    assert status_events_response.status_code == 200
    status_items = status_events_response.json()["items"]
    assert status_items
    assert all(item["status"] == "sent" for item in status_items)


def test_operational_events_endpoint_includes_runs_when_requested(
    client: TestClient, monkeypatch
):
    """?include_runs=true must return both run and run_event rows."""
    bootstrap_operator(client)
    newsletter = create_newsletter(client)
    _stub_generation_and_delivery(monkeypatch)

    run_response = client.post(f"/api/newsletters/{newsletter['id']}/run")
    assert run_response.status_code == 200
    delivery_run = run_response.json()["run"]

    events_response = client.get(
        "/api/runs/events",
        params={"search": newsletter["name"], "include_runs": "true"},
    )
    assert events_response.status_code == 200
    items = events_response.json()["items"]
    assert items

    sources = {item["source"] for item in items}
    assert "run" in sources, "include_runs=true response must include run-source entries"
    assert "run_event" in sources, "include_runs=true response must include run_event-source entries"
    assert any(item["run_id"] == delivery_run["id"] for item in items)

    run_items = [
        item
        for item in items
        if item["source"] == "run" and item["run_id"] == delivery_run["id"]
    ]
    assert run_items
    assert run_items[0]["event_type"] == "run-manual-run"
    assert run_items[0]["status"] == delivery_run["run_status"]
    assert run_items[0]["related_entity"].endswith(f"Run #{delivery_run['id']}")
