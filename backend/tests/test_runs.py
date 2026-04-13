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
            "draft_subject": "Scheduler Brief",
            "draft_preheader": "Recurring operations pulse",
            "draft_body_text": "Recurring story block",
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


def test_schedule_controls_enable_and_disable_newsletter_schedule(client: TestClient):
    bootstrap_operator(client)
    newsletter = create_newsletter(client)

    resume_response = client.post(f"/api/newsletters/{newsletter['id']}/schedule/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["schedule_enabled"] is True

    pause_response = client.post(f"/api/newsletters/{newsletter['id']}/schedule/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["schedule_enabled"] is False


def test_run_dashboard_filters_and_details(client: TestClient):
    bootstrap_operator(client)
    newsletter = create_newsletter(client)

    generate_response = client.post(f"/api/newsletters/{newsletter['id']}/generate-draft")
    assert generate_response.status_code == 200

    send_response = client.post(f"/api/newsletters/{newsletter['id']}/send")
    assert send_response.status_code == 200
    send_run_id = send_response.json()["run"]["id"]

    runs_response = client.get(
        "/api/runs",
        params={"newsletter_id": newsletter["id"], "trigger_mode": "manual-send"},
    )
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["items"]
    assert all(item["trigger_mode"] == "manual-send" for item in runs_payload["items"])

    run_detail_response = client.get(f"/api/runs/{send_run_id}")
    assert run_detail_response.status_code == 200
    detail_payload = run_detail_response.json()
    assert detail_payload["run"]["id"] == send_run_id
    assert detail_payload["run"]["snapshot_subject"]
    assert detail_payload["recipient_outcomes"]

    reconcile_response = client.post(f"/api/runs/{send_run_id}/reconcile")
    assert reconcile_response.status_code == 200
    reconcile_payload = reconcile_response.json()
    assert reconcile_payload["events"]

    refreshed_detail = client.get(f"/api/runs/{send_run_id}")
    assert refreshed_detail.status_code == 200
    assert refreshed_detail.json()["events"]


def test_duplicate_manual_send_reuses_existing_run(client: TestClient):
    bootstrap_operator(client)
    newsletter = create_newsletter(client)

    first_send = client.post(f"/api/newsletters/{newsletter['id']}/send")
    assert first_send.status_code == 200
    first_run = first_send.json()["run"]

    second_send = client.post(f"/api/newsletters/{newsletter['id']}/send")
    assert second_send.status_code == 200
    second_run = second_send.json()["run"]

    assert second_run["id"] == first_run["id"]
    assert second_run["revision_id"] == first_run["revision_id"]


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


def test_operational_events_endpoint_defaults_to_run_events_only(client: TestClient):
    bootstrap_operator(client)
    newsletter = create_newsletter(client)

    generate_response = client.post(f"/api/newsletters/{newsletter['id']}/generate-draft")
    assert generate_response.status_code == 200

    send_response = client.post(f"/api/newsletters/{newsletter['id']}/send")
    assert send_response.status_code == 200
    send_run = send_response.json()["run"]

    events_response = client.get(
        "/api/runs/events",
        params={"search": newsletter["name"]},
    )
    assert events_response.status_code == 200

    items = events_response.json()["items"]
    assert items
    assert all(item["source"] == "run_event" for item in items)
    assert any(item["run_id"] == send_run["id"] for item in items)

    run_feed_response = client.get(
        "/api/runs/events",
        params={"search": newsletter["name"], "include_runs": True},
    )
    assert run_feed_response.status_code == 200
    run_feed_items = run_feed_response.json()["items"]
    assert any(item["source"] == "run" for item in run_feed_items)

    run_items = [
        item
        for item in run_feed_items
        if item["source"] == "run" and item["run_id"] == send_run["id"]
    ]
    assert run_items
    assert run_items[0]["event_type"] == "run-manual-send"
    assert run_items[0]["status"] == send_run["run_status"]
    assert run_items[0]["related_entity"].endswith(f"Run #{send_run['id']}")

    generation_events_response = client.get(
        "/api/runs/events",
        params={"event_type": "generation"},
    )
    assert generation_events_response.status_code == 200
    generation_items = generation_events_response.json()["items"]
    assert generation_items
    assert all(item["source"] == "run_event" for item in generation_items)
    assert all(item["event_type"] == "generation" for item in generation_items)

    status_events_response = client.get(
        "/api/runs/events",
        params={"status": send_run["run_status"]},
    )
    assert status_events_response.status_code == 200
    status_items = status_events_response.json()["items"]
    assert status_items
    assert all(item["status"] == send_run["run_status"] for item in status_items)
