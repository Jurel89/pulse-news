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
    import app.scheduler
    import app.schemas

    app.config.get_settings.cache_clear()
    app.database.get_engine.cache_clear()
    app.database.get_session_maker.cache_clear()

    reload(app.config)
    reload(app.database)
    reload(app.models)
    reload(app.scheduler)
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

    app.scheduler._scheduler = None


def create_newsletter_record(**overrides):
    import app.database
    from app.models import Newsletter

    values = {
        "name": "Scheduler Brief",
        "slug": f"scheduler-brief-{overrides.get('slug_suffix', 'default')}",
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
        "schedule_cron": "0 7 * * 1-5",
        "schedule_enabled": True,
        "status": "active",
    }
    values.update(overrides)
    values.pop("slug_suffix", None)

    session = app.database.get_session_maker()()
    try:
        newsletter = Newsletter(**values)
        session.add(newsletter)
        session.commit()
        session.refresh(newsletter)
        return newsletter
    finally:
        session.close()


def test_scheduler_starts_on_app_lifespan_and_can_shutdown(client: TestClient):
    import app.scheduler

    scheduler = app.scheduler.get_scheduler()

    assert scheduler.running is True

    app.scheduler.shutdown_scheduler()

    assert scheduler.running is False


def test_sync_newsletter_schedule_adds_and_removes_jobs(client: TestClient):
    import app.database
    import app.scheduler

    newsletter = create_newsletter_record(slug_suffix="scheduled")
    scheduler = app.scheduler.get_scheduler()
    job_id = app.scheduler.newsletter_job_id(newsletter.id)

    app.scheduler.sync_newsletter_schedule(newsletter)

    scheduled_job = scheduler.get_job(job_id)
    assert scheduled_job is not None
    assert scheduled_job.id == job_id
    assert scheduled_job.args == (newsletter.id,)
    assert scheduled_job.max_instances == 1

    session = app.database.get_session_maker()()
    try:
        stored_newsletter = session.get(type(newsletter), newsletter.id)
        assert stored_newsletter is not None
        stored_newsletter.schedule_enabled = False
        session.commit()
        session.refresh(stored_newsletter)
    finally:
        session.close()

    app.scheduler.sync_newsletter_schedule(stored_newsletter)

    assert scheduler.get_job(job_id) is None


def test_sync_newsletter_schedule_skips_newsletters_without_cron(client: TestClient):
    import app.scheduler

    newsletter = create_newsletter_record(
        slug_suffix="no-cron",
        schedule_cron=None,
        schedule_enabled=True,
    )

    app.scheduler.sync_newsletter_schedule(newsletter)

    assert (
        app.scheduler.get_scheduler().get_job(app.scheduler.newsletter_job_id(newsletter.id))
        is None
    )
