from __future__ import annotations

from importlib import reload
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PULSE_NEWS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PULSE_NEWS_SECRET_KEY", "test-secret")
    monkeypatch.setenv("PULSE_NEWS_ENVIRONMENT", "development")

    import app.ai_generation
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
    reload(app.ai_generation)
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
        "name": "Weekly Radar",
        "slug": "weekly-radar",
        "description": "Founder signals worth scanning",
        "prompt": "Summarize the top AI and startup operations stories for founders.",
        "draft_subject": "",
        "draft_preheader": "",
        "draft_body_text": "",
        "provider_name": " OpenAI ",
        "model_name": "gpt-4o-mini",
        "template_key": "signal",
        "audience_name": "founders",
        "delivery_topic": "weekly-radar",
        "timezone": "UTC",
        "schedule_enabled": False,
        "status": "active",
    }
    values.update(overrides)
    return Newsletter(**values)


def make_completion_response(content: str) -> Mock:
    message = Mock()
    message.content = content
    choice = Mock()
    choice.message = message
    response = Mock()
    response.choices = [choice]
    return response


def test_generate_newsletter_draft_uses_litellm_when_provider_credentials_exist(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation

    newsletter = build_newsletter()
    completion_mock = Mock(
        return_value=make_completion_response(
            "SUBJECT: Founder Radar\n"
            "PREHEADER: The week in startup infrastructure\n"
            "BODY:\n"
            "- Fundraising signals\n"
            "- Ops playbook updates"
        )
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_has_live_provider_credentials",
        Mock(return_value=True),
    )

    result = app.ai_generation.generate_newsletter_draft(newsletter)

    assert result.status == "generated"
    assert result.mode == "litellm"
    assert result.subject == "Founder Radar"
    assert result.preheader == "The week in startup infrastructure"
    assert result.body_text == "- Fundraising signals\n- Ops playbook updates"
    completion_mock.assert_called_once()
    assert completion_mock.call_args.kwargs["model"] == "openai/gpt-4o-mini"
    assert "Prompt instructions:" in completion_mock.call_args.kwargs["messages"][0]["content"]


def test_generate_newsletter_draft_returns_fallback_when_litellm_raises(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation

    newsletter = build_newsletter()
    monkeypatch.setattr(
        app.ai_generation,
        "completion",
        Mock(side_effect=RuntimeError("provider unavailable")),
    )
    monkeypatch.setattr(
        app.ai_generation,
        "_has_live_provider_credentials",
        Mock(return_value=True),
    )

    result = app.ai_generation.generate_newsletter_draft(newsletter)

    assert result.status == "fallback"
    assert result.mode == "local-generator"
    assert result.subject == "Weekly Radar: generated draft"
    assert result.preheader == "Founder signals worth scanning"
    assert "Live generation failed, using local fallback instead" in result.message
    assert "Fallback draft outline" in result.body_text


def test_generate_newsletter_draft_parses_subject_preheader_and_body_sections(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation

    newsletter = build_newsletter(description="Fallback description")
    completion_mock = Mock(
        return_value=make_completion_response(
            "SUBJECT:   Operator Watch  \n"
            "PREHEADER:  Signals worth scanning  \n"
            "BODY:\n"
            "First section\n"
            "\n"
            "Second section"
        )
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_has_live_provider_credentials",
        Mock(return_value=True),
    )

    result = app.ai_generation.generate_newsletter_draft(newsletter)

    assert result.subject == "Operator Watch"
    assert result.preheader == "Signals worth scanning"
    assert result.body_text == "First section\n\nSecond section"
