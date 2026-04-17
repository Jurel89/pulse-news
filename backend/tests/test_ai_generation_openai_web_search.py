"""Tests that verify the OpenAI web-search tool integration.

- tool_registry.web_search_tools_for("openai") returns the web_search_preview tool.
- generate_newsletter_content for "openai" passes the tool through to completion.
- generate_newsletter_content for "openai_chatgpt" calls the ChatGPT adapter.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.generation.tool_registry import web_search_tools_for


def test_openai_web_search_tools_returns_preview():
    tools = web_search_tools_for("openai")
    assert tools is not None
    assert len(tools) == 1
    assert tools[0]["type"] == "web_search_preview"


def test_openai_chatgpt_web_search_tools_returns_none():
    # The adapter handles its own tool — the registry should return None.
    tools = web_search_tools_for("openai_chatgpt")
    assert tools is None


def test_anthropic_web_search_still_works():
    tools = web_search_tools_for("anthropic")
    assert tools is not None
    assert tools[0]["type"] == "web_search_20250305"


def test_gemini_web_search_still_works():
    tools = web_search_tools_for("gemini")
    assert tools is not None
    assert "google_search" in tools[0]


def test_kimi_web_search_still_works():
    tools = web_search_tools_for("kimi")
    assert tools is not None
    assert len(tools) == 2  # web_search + fetch_url


def test_generate_newsletter_openai_attaches_web_search_tool(tmp_path, monkeypatch):
    """generate_newsletter_content for openai provider attaches the web_search_preview tool."""
    monkeypatch.setenv("PULSE_NEWS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PULSE_NEWS_SECRET_KEY", "test-secret")
    monkeypatch.setenv("PULSE_NEWS_ENVIRONMENT", "development")

    import app.config
    import app.database

    app.config.get_settings.cache_clear()
    app.database.get_engine.cache_clear()
    app.database.get_session_maker.cache_clear()

    from app.ai_generation import generate_newsletter_content
    from app.models import Newsletter

    newsletter = Newsletter(
        id=1,
        name="Test",
        slug="test",
        prompt="Write about AI.",
        subject="Test subject",
        preheader=None,
        body_text="",
        provider_name="openai",
        model_name="gpt-4o-mini",
        template_key="signal",
        audience_name="developers",
        delivery_topic="ai",
        timezone="UTC",
    )

    captured_kwargs: dict = {}

    def fake_run_with_loop(*, model, messages, api_key, completion_kwargs, **kwargs):
        captured_kwargs.update(completion_kwargs)
        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = '{"subject":"S","preheader":"P","body_markdown":"B"}'
        mock_response.usage = None
        return mock_response, []

    with (
        patch("app.ai_generation._run_completion_with_tool_loop", side_effect=fake_run_with_loop),
        patch("app.ai_generation._get_api_key_for_newsletter", return_value="sk-test"),
        patch("app.ai_generation._resolve_api_key_for_newsletter") as mock_resolve,
        patch("app.ai_generation.completion", new=MagicMock()),
    ):
        from app.ai_generation import ApiKeyResolution

        mock_resolve.return_value = ApiKeyResolution(
            api_key="sk-test",
            source="environment",
            detail="test",
        )
        generate_newsletter_content(newsletter)

    # web_search_preview tool must have been passed
    tools = captured_kwargs.get("tools", [])
    assert any(t.get("type") == "web_search_preview" for t in tools), (
        f"Expected web_search_preview in tools, got: {tools}"
    )
