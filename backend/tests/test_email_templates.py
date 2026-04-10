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
    import app.email_templates
    import app.main
    import app.models
    import app.schemas

    app.config.get_settings.cache_clear()
    app.database.get_engine.cache_clear()
    app.database.get_session_maker.cache_clear()

    reload(app.config)
    reload(app.database)
    reload(app.models)
    reload(app.email_templates)
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


def build_newsletter(**overrides):
    from app.models import Newsletter

    values = {
        "name": "Template Brief",
        "slug": "template-brief",
        "description": "Signals and notes for operators",
        "prompt": "Generate the weekly template preview.",
        "draft_subject": "Template Brief",
        "draft_preheader": "Signals and notes for operators",
        "draft_body_text": "Line one\n\nLine two",
        "provider_name": "openai",
        "model_name": "gpt-4o-mini",
        "template_key": "signal",
        "audience_name": "ops",
        "delivery_topic": "template-brief",
        "timezone": "UTC",
        "schedule_enabled": False,
        "status": "active",
    }
    values.update(overrides)
    return Newsletter(**values)


def test_render_newsletter_produces_html_and_plain_text(client: TestClient):
    import app.email_templates

    rendered = app.email_templates.render_newsletter(build_newsletter())

    assert rendered.html.startswith("<!doctype html>")
    assert "<html>" in rendered.html
    assert rendered.html.endswith("</html>")
    assert rendered.plain_text == (
        "Template Brief\nSignals and notes for operators\n\nLine one\n\nLine two"
    )


@pytest.mark.parametrize("template_key", ["signal", "ledger"])
def test_each_template_key_renders_without_error(client: TestClient, template_key: str):
    import app.email_templates

    rendered = app.email_templates.render_newsletter(build_newsletter(template_key=template_key))

    assert rendered.template_key == template_key
    assert rendered.subject == "Template Brief"
    assert "Line one" in rendered.html
    assert "Line one" in rendered.plain_text


def test_rendered_output_contains_expected_subject_and_body_text(client: TestClient):
    import app.email_templates

    rendered = app.email_templates.render_newsletter(
        build_newsletter(
            draft_subject="Ops & Markets",
            draft_preheader="Signals <and> notes",
            draft_body_text="First <line>\n\nSecond & final",
        )
    )

    assert "Ops &amp; Markets" in rendered.html
    assert "Signals &lt;and&gt; notes" in rendered.html
    assert "First &lt;line&gt;" in rendered.html
    assert "Second &amp; final" in rendered.html
    assert "Ops & Markets" in rendered.plain_text
    assert "Signals <and> notes" in rendered.plain_text
    assert "First <line>" in rendered.plain_text
    assert "Second & final" in rendered.plain_text
