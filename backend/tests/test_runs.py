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
            "timezone": "UTC",
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
