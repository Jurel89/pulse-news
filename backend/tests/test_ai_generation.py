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
        "prompt": "Summarize the top AI and startup operations stories for founders using https://example.com/source.",
        "subject": "",
        "preheader": "",
        "body_text": "",
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


def make_api_key_resolution(*, api_key: str | None, detail: str = "Using test API key"):
    import app.ai_generation

    return app.ai_generation.ApiKeyResolution(
        api_key=api_key,
        source="test",
        detail=detail,
    )


def test_generate_newsletter_content_uses_litellm_when_provider_credentials_exist(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation

    newsletter = build_newsletter()
    completion_mock = Mock(
        return_value=make_completion_response(
            "{"
            '"subject":"Founder Radar",'
            '"preheader":"The week in startup infrastructure",'
            '"body_markdown":"- Fundraising signals\\n- Ops playbook updates"'
            "}"
        )
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "generated"
    assert result.mode == "litellm"
    assert result.subject == "Founder Radar"
    assert result.preheader == "The week in startup infrastructure"
    assert result.body_text == "- Fundraising signals\n- Ops playbook updates"
    completion_mock.assert_called_once()
    assert completion_mock.call_args.kwargs["model"] == "openai/gpt-4o-mini"
    prompt_text = completion_mock.call_args.kwargs["messages"][0]["content"]
    assert "Instructions:" in prompt_text
    assert "Write the newsletter with:" in prompt_text
    assert '{"subject":"...","preheader":"...","body_markdown":"..."}' in prompt_text


def test_generate_newsletter_content_returns_error_when_litellm_raises_by_default(
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
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "error"
    assert result.mode == "none"
    assert result.subject == "Weekly Radar"
    assert result.preheader == "Founder signals worth scanning"
    assert "Live generation failed for provider 'openai'" in result.message
    assert "provider unavailable" in result.message
    assert result.body_text == ""


def test_generate_newsletter_content_returns_error_when_api_key_is_unavailable(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation

    newsletter = build_newsletter()
    monkeypatch.setattr(app.ai_generation, "completion", Mock())
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(
            return_value=make_api_key_resolution(
                api_key=None,
                detail="The selected newsletter API key is inactive.",
            )
        ),
    )

    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "error"
    assert result.mode == "none"
    assert "inactive" in result.message


def test_generate_newsletter_content_rejects_non_json_output(
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
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "error"
    assert result.mode == "litellm"
    assert "strict JSON" in result.message


def test_generate_newsletter_content_accepts_structured_json_output(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation

    newsletter = build_newsletter(description="Fallback description")
    completion_mock = Mock(
        return_value=make_completion_response(
            "{"
            '"subject":"Operator Watch",'
            '"preheader":"Signals worth scanning",'
            '"body_markdown":"First section\\n\\nSecond section"'
            "}"
        )
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.subject == "Operator Watch"
    assert result.preheader == "Signals worth scanning"
    assert result.body_text == "First section\n\nSecond section"


def test_generate_newsletter_content_accepts_json_wrapped_in_markdown_fences(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation

    newsletter = build_newsletter(description="Fallback description")
    completion_mock = Mock(
        return_value=make_completion_response(
            "```json\n"
            "{"
            '"subject":"Fenced Output",'
            '"preheader":"Wrapped by the model",'
            '"body_markdown":"Body copy"'
            "}"
            "\n```"
        )
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "generated"
    assert result.subject == "Fenced Output"
    assert result.preheader == "Wrapped by the model"
    assert result.body_text == "Body copy"


def test_generate_newsletter_content_rejects_subjects_longer_than_limit(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation

    newsletter = build_newsletter(description="Fallback description")
    completion_mock = Mock(
        return_value=make_completion_response(
            "{"
            f'"subject":"{"x" * 121}",'
            '"preheader":"Signals worth scanning",'
            '"body_markdown":"- Section one"'
            "}"
        )
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "error"
    assert "120 character limit" in result.message


def test_generate_newsletter_content_rejects_unsupported_template_variables(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation

    newsletter = build_newsletter(description="Fallback description")
    completion_mock = Mock(
        return_value=make_completion_response(
            "{"
            '"subject":"Operator Watch",'
            '"preheader":"Signals worth scanning",'
            '"body_markdown":"- Hello %recipient_name%"'
            "}"
        )
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "error"
    assert "unsupported template variables" in result.message


def test_generate_newsletter_content_uses_provider_defaults_and_pinned_database_key(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation
    from app.database import get_session_maker
    from app.models import ApiKey, Provider

    session = get_session_maker()()
    provider = Provider(
        name="Primary OpenAI",
        provider_type="openai",
        is_enabled=True,
        default_model="gpt-4o",
        configuration='{"temperature": 0.25, "max_tokens": 600}',
    )
    api_key = ApiKey(
        name="Team OpenAI Key",
        provider_type="openai",
        key_value="db-openai-key",
        is_active=True,
    )
    session.add_all([provider, api_key])
    session.commit()
    session.refresh(provider)
    session.refresh(api_key)
    api_key_id = api_key.id
    session.close()

    newsletter = build_newsletter(provider_id=provider.id, model_name="", api_key_id=api_key_id)
    newsletter.provider = provider

    completion_mock = Mock(
        return_value=make_completion_response(
            "{"
            '"subject":"Provider Defaults",'
            '"preheader":"Configured by provider",'
            '"body_markdown":"- Uses the provider default model"'
            "}"
        )
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)

    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "generated"
    assert completion_mock.call_args.kwargs["model"] == "openai/gpt-4o"
    assert completion_mock.call_args.kwargs["api_key"] == "db-openai-key"
    assert completion_mock.call_args.kwargs["temperature"] == 0.25
    assert "max_tokens" not in completion_mock.call_args.kwargs


def test_generate_newsletter_content_returns_error_for_invalid_provider_configuration(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation
    from app.models import Provider

    newsletter = build_newsletter()
    newsletter.provider = Provider(
        name="Broken OpenAI",
        provider_type="openai",
        is_enabled=True,
        default_model="gpt-4o-mini",
        configuration='["not", "an", "object"]',
    )

    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "error"
    assert result.mode == "none"
    assert result.message == "Provider configuration must be a JSON object."


def test_generate_newsletter_content_fails_closed_for_inactive_pinned_key(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation
    from app.database import get_session_maker
    from app.models import ApiKey

    session = get_session_maker()()
    api_key = ApiKey(
        name="Inactive OpenAI Key",
        provider_type="openai",
        key_value="db-openai-key",
        is_active=False,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    api_key_id = api_key.id
    session.close()

    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    completion_mock = Mock()
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)

    newsletter = build_newsletter(api_key_id=api_key_id)
    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "error"
    assert result.mode == "none"
    assert "Inactive OpenAI Key" in result.message
    assert "inactive" in result.message
    completion_mock.assert_not_called()


def test_kimi_provider_uses_coding_api_base_url(client: TestClient, monkeypatch):
    import app.ai_generation
    from app.models import Provider

    newsletter = build_newsletter(provider_name="kimi", model_name="kimi-k2.5")
    provider = Provider(
        name="Kimi",
        provider_type="kimi",
        is_enabled=True,
        default_model="kimi-k2.5",
    )
    newsletter.provider = provider
    newsletter.provider_id = None

    completion_mock = Mock(
        return_value=make_completion_response(
            '{"subject":"Test","preheader":"Test","body_markdown":"Content"}'
        )
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    app.ai_generation.generate_newsletter_content(newsletter)

    assert completion_mock.call_args.kwargs["model"] == "moonshot/kimi-k2.5"
    assert completion_mock.call_args.kwargs["api_base"] == "https://api.kimi.com/coding/v1"
    assert completion_mock.call_args.kwargs["extra_headers"]["User-Agent"] == "claude-code/0.1.0"


def test_kimi_user_agent_merges_with_existing_extra_headers(client: TestClient, monkeypatch):
    import app.ai_generation
    from app.models import Provider

    newsletter = build_newsletter(provider_name="kimi", model_name="kimi-k2.5")
    provider = Provider(
        name="Kimi",
        provider_type="kimi",
        is_enabled=True,
        default_model="kimi-k2.5",
        configuration='{"extra_headers": {"X-Custom": "value"}}',
    )
    newsletter.provider = provider
    newsletter.provider_id = None

    completion_mock = Mock(
        return_value=make_completion_response('{"subject":"T","preheader":"T","body_markdown":"C"}')
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    app.ai_generation.generate_newsletter_content(newsletter)

    headers = completion_mock.call_args.kwargs["extra_headers"]
    assert headers["User-Agent"] == "claude-code/0.1.0"
    assert headers["X-Custom"] == "value"
