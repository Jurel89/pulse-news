from __future__ import annotations

import json
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
    # Without a concrete current date, Kimi anchors to its training cutoff
    # and produces stale news. Enforce that today's date is injected.
    from datetime import UTC, datetime

    assert datetime.now(UTC).date().isoformat() in prompt_text
    assert "Today is " in prompt_text


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


def test_generate_newsletter_content_enables_client_side_web_search_for_kimi(
    client: TestClient,
    monkeypatch,
):
    """The Kimi Coding API has no server-resolved web search. We declare a
    plain function tool that we resolve client-side instead."""
    import app.ai_generation

    newsletter = build_newsletter(provider_name="kimi", model_name="kimi-k2.5")
    completion_mock = Mock(
        return_value=make_completion_response('{"subject":"s","preheader":"p","body_markdown":"b"}')
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    app.ai_generation.generate_newsletter_content(newsletter)

    tools = completion_mock.call_args.kwargs.get("tools")
    assert tools is not None
    tool_names = {t["function"]["name"] for t in tools if t.get("type") == "function"}
    assert "web_search" in tool_names
    web_search_tool = next(t for t in tools if t["function"]["name"] == "web_search")
    assert "query" in web_search_tool["function"]["parameters"]["properties"]


@pytest.mark.parametrize(
    "provider_type, expected_tool",
    [
        (
            "anthropic",
            {"type": "web_search_20250305", "name": "web_search"},
        ),
        (
            "gemini",
            {"google_search": {}},
        ),
    ],
)
def test_generate_newsletter_content_uses_native_server_resolved_tool_for_one_shot_providers(
    client: TestClient,
    monkeypatch,
    provider_type: str,
    expected_tool: dict,
):
    import app.ai_generation

    newsletter = build_newsletter(provider_name=provider_type, model_name="test-model")
    completion_mock = Mock(
        return_value=make_completion_response('{"subject":"s","preheader":"p","body_markdown":"b"}')
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    app.ai_generation.generate_newsletter_content(newsletter)

    tools = completion_mock.call_args.kwargs.get("tools")
    assert tools == [expected_tool]


def test_tool_loop_force_closes_without_tools_when_max_iterations_reached(
    client: TestClient,
):
    """If the model keeps asking for tools past max_iterations, the loop must
    make one final call with ``tools`` stripped so the model is forced to
    return content. Otherwise the caller sees an empty response and can't
    distinguish \"model gave up\" from \"model loop wasn't closed out\"."""
    from app.generation import tool_loop

    def make_tool_response():
        tc = Mock()
        tc.id = "call_x"
        tc.function = Mock()
        tc.function.name = "web_search"
        tc.function.arguments = '{"query": "ai"}'
        msg = Mock()
        msg.content = None
        msg.tool_calls = [tc]
        choice = Mock()
        choice.message = msg
        choice.finish_reason = "tool_calls"
        resp = Mock()
        resp.choices = [choice]
        resp.usage = None
        return resp

    def make_final_response():
        msg = Mock()
        msg.content = '{"subject":"S","preheader":"P","body_markdown":"B"}'
        msg.tool_calls = None
        choice = Mock()
        choice.message = msg
        choice.finish_reason = "stop"
        resp = Mock()
        resp.choices = [choice]
        resp.usage = None
        return resp

    # 3 iterations + 1 forced close after max_iterations=2.
    responses = [
        make_tool_response(),
        make_tool_response(),
        make_tool_response(),
        make_final_response(),
    ]
    completion_mock = Mock(side_effect=responses)

    final_response, trace = tool_loop.run(
        completion=completion_mock,
        model="kimi/kimi-k2.5",
        messages=[{"role": "user", "content": "write me a newsletter"}],
        api_key="k",
        completion_kwargs={"tools": [{"type": "function", "function": {"name": "web_search"}}]},
        max_iterations=2,
        tool_executor=lambda name, args: '{"results":[]}',
    )

    # Last completion call is the force-close — no tools kwarg.
    last_call_kwargs = completion_mock.call_args_list[-1].kwargs
    assert "tools" not in last_call_kwargs, (
        "Force-close call must strip the tools kwarg so the model has to respond."
    )
    # Trace records the force-close marker.
    assert trace[-1].get("force_closed") is True
    # Final response is the one from the force-close, with real content.
    assert final_response.choices[0].message.content.startswith("{")


def test_generate_newsletter_content_executes_client_side_web_search_for_kimi(
    client: TestClient,
    monkeypatch,
):
    """When Kimi returns tool_calls for our web_search function, we must
    actually run the search (DDG) and feed real results back — not echo the
    arguments like the Moonshot $web_search builtin required."""
    import app.ai_generation

    newsletter = build_newsletter(provider_name="kimi", model_name="kimi-k2.5")

    tool_call = Mock()
    tool_call.id = "call_abc"
    tool_call.function = Mock()
    tool_call.function.name = "web_search"
    tool_call.function.arguments = '{"query": "latest AI news", "max_results": 3}'

    # First round: model asks us to run the search.
    first_message = Mock()
    first_message.content = None
    first_message.tool_calls = [tool_call]
    first_choice = Mock()
    first_choice.message = first_message
    first_choice.finish_reason = "tool_calls"
    first_response = Mock()
    first_response.choices = [first_choice]
    first_response.usage = None

    # Second round: model produces the final newsletter with the search data.
    second_response = make_completion_response(
        '{"subject":"From Web","preheader":"Real news","body_markdown":"Recent stuff."}'
    )

    completion_mock = Mock(side_effect=[first_response, second_response])
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    # Stub out the real DDG call so tests run offline and deterministically.
    monkeypatch.setattr(
        app.ai_generation,
        "_execute_client_side_tool_call",
        Mock(
            return_value=(
                '{"query": "latest AI news", "results": ['
                '{"title": "Big AI launch", "url": "https://example.com/ai", '
                '"snippet": "A major AI company shipped X today."}'
                "]}"
            )
        ),
    )

    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "generated"
    assert result.subject == "From Web"
    assert completion_mock.call_count == 2

    second_call_messages = completion_mock.call_args_list[1].kwargs["messages"]
    tool_message = next(m for m in second_call_messages if m.get("role") == "tool")
    assert tool_message["tool_call_id"] == "call_abc"
    assert tool_message["name"] == "web_search"
    # The tool message content should be the *executed* search result, not
    # an echo of the arguments — that's the whole point of this round-trip.
    assert "Big AI launch" in tool_message["content"]
    assert tool_message["content"] != '{"query": "latest AI news", "max_results": 3}'


def test_execute_client_side_tool_call_returns_error_on_invalid_json(
    client: TestClient,
):
    import app.ai_generation

    result = app.ai_generation._execute_client_side_tool_call("web_search", "{not json")
    assert "invalid tool arguments json" in result


def test_kimi_tools_payload_includes_fetch_url(
    client: TestClient,
    monkeypatch,
):
    """Kimi should be offered both web_search (discovery) and fetch_url
    (verification) so it can quote from sources instead of inventing
    details based on search snippets alone."""
    import app.ai_generation

    newsletter = build_newsletter(provider_name="kimi", model_name="kimi-k2.5")
    completion_mock = Mock(
        return_value=make_completion_response('{"subject":"s","preheader":"p","body_markdown":"b"}')
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    app.ai_generation.generate_newsletter_content(newsletter)

    tools = completion_mock.call_args.kwargs.get("tools") or []
    tool_names = {t.get("function", {}).get("name") for t in tools if t.get("type") == "function"}
    assert "web_search" in tool_names
    assert "fetch_url" in tool_names


def test_execute_client_side_tool_call_dispatches_fetch_url(
    client: TestClient,
    monkeypatch,
):
    """The ai_generation dispatcher must route fetch_url calls to the
    fetch_url executor, not to web_search."""
    import app.ai_generation
    from app.generation import fetch_url

    fake = Mock(return_value='{"ok": true}')
    monkeypatch.setattr(fetch_url, "execute", fake)

    result = app.ai_generation._execute_client_side_tool_call(
        "fetch_url", '{"url": "https://example.com"}'
    )
    fake.assert_called_once_with("fetch_url", '{"url": "https://example.com"}')
    assert result == '{"ok": true}'


def test_fetch_url_tool_executes_http_get_and_returns_cleaned_content(
    client: TestClient,
    monkeypatch,
):
    """fetch_url should GET the url, strip scripts/styles/tags, extract the
    page title, and return a compact JSON payload the model can quote from."""
    from app.generation import fetch_url

    html = b"""
    <html>
      <head>
        <title>   Test Page   </title>
        <style>.x { color: red; }</style>
        <script>alert(1);</script>
      </head>
      <body>
        <h1>Hello</h1>
        <p>The &amp; in HTML must decode.</p>
      </body>
    </html>
    """.strip()

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def read(self, _limit):
            return html

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: FakeResponse(),
    )

    result = fetch_url.execute("fetch_url", '{"url": "https://example.com/post"}')
    parsed = json.loads(result)
    assert parsed["status"] == 200
    assert parsed["title"] == "Test Page"
    assert "Hello" in parsed["content"]
    assert "The & in HTML must decode." in parsed["content"]
    assert "alert(1)" not in parsed["content"]
    assert "color: red" not in parsed["content"]


def test_fetch_url_tool_rejects_non_http_urls(client: TestClient):
    from app.generation import fetch_url

    result = fetch_url.execute("fetch_url", '{"url": "file:///etc/passwd"}')
    assert "must start with http" in result

    result = fetch_url.execute("fetch_url", "{}")
    assert "missing required argument: url" in result


def test_execute_client_side_tool_call_rejects_unknown_tool_names(
    client: TestClient,
):
    import app.ai_generation

    result = app.ai_generation._execute_client_side_tool_call("sudo_rm_rf", '{"x":1}')
    assert "unknown tool" in result


def test_execute_client_side_tool_call_runs_ddg_and_shapes_results(
    client: TestClient,
    monkeypatch,
):
    """The executor must call DDGS().text() with the query and return a
    compact JSON string the model can use as tool output."""
    import app.ai_generation

    fake_ddgs = Mock()
    fake_ddgs.__enter__ = Mock(return_value=fake_ddgs)
    fake_ddgs.__exit__ = Mock(return_value=False)
    fake_ddgs.text = Mock(
        return_value=[
            {
                "title": "Big AI launch",
                "href": "https://example.com/ai",
                "body": "A major launch this week.",
            }
        ]
    )
    monkeypatch.setattr("ddgs.DDGS", lambda: fake_ddgs)

    result = app.ai_generation._execute_client_side_tool_call(
        "web_search", '{"query": "ai news", "max_results": 3}'
    )
    parsed = json.loads(result)
    assert parsed["query"] == "ai news"
    assert parsed["results"] == [
        {
            "title": "Big AI launch",
            "url": "https://example.com/ai",
            "snippet": "A major launch this week.",
        }
    ]
    fake_ddgs.text.assert_called_once_with("ai news", max_results=3)


def test_generate_newsletter_content_passes_web_search_preview_for_openai(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation

    newsletter = build_newsletter(provider_name="openai", model_name="gpt-4o-mini")
    completion_mock = Mock(
        return_value=make_completion_response('{"subject":"s","preheader":"p","body_markdown":"b"}')
    )
    monkeypatch.setattr(app.ai_generation, "completion", completion_mock)
    monkeypatch.setattr(
        app.ai_generation,
        "_resolve_api_key_for_newsletter",
        Mock(return_value=make_api_key_resolution(api_key="test-key")),
    )

    app.ai_generation.generate_newsletter_content(newsletter)

    # OpenAI Chat Completions supports web_search_preview as a server-resolved tool.
    tools = completion_mock.call_args.kwargs.get("tools")
    assert tools is not None
    assert any(t.get("type") == "web_search_preview" for t in tools)


def test_generate_newsletter_content_extracts_json_from_prose_prefix_and_suffix(
    client: TestClient,
    monkeypatch,
):
    """After a tool round-trip, Kimi sometimes prefaces the JSON with
    ``Here is the newsletter:`` or appends trailing prose. The parser should
    still recover by picking the outermost balanced {...} object."""
    import app.ai_generation

    newsletter = build_newsletter(description="Fallback description")
    completion_mock = Mock(
        return_value=make_completion_response(
            "Here is the newsletter you requested:\n\n"
            '{"subject":"Recovered","preheader":"From the web",'
            '"body_markdown":"# Title\\n\\nBody."}'
            "\n\nLet me know if you want changes."
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
    assert result.subject == "Recovered"
    assert result.body_text == "# Title\n\nBody."


def test_generate_newsletter_content_parse_failure_includes_raw_preview(
    client: TestClient,
    monkeypatch,
):
    """When the model returns something the parser can't recover, the error
    message must include the raw response so operators can see *why* from the
    Logs page without tailing docker or adding more debug code."""
    import app.ai_generation

    newsletter = build_newsletter(description="d")
    completion_mock = Mock(
        return_value=make_completion_response(
            "I cannot produce JSON for this request because blah blah."
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
    assert "could not be parsed" in result.message
    assert "I cannot produce JSON" in result.message


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


def test_chatgpt_oauth_falls_back_to_active_when_pinned_is_inactive(
    client: TestClient,
    monkeypatch,
):
    import app.ai_generation
    from app.database import get_session_maker
    from app.models import ApiKey

    session = get_session_maker()()

    inactive_pinned = ApiKey(
        name="Inactive ChatGPT OAuth",
        provider_type="openai_chatgpt",
        auth_type="oauth",
        key_value="sentinel-inactive",
        is_active=False,
        oauth_access_token="enc-old-token",
        oauth_refresh_token="enc-old-refresh",
    )
    active_fallback = ApiKey(
        name="Active ChatGPT OAuth",
        provider_type="openai_chatgpt",
        auth_type="oauth",
        key_value="sentinel-active",
        is_active=True,
        oauth_access_token="enc-active-token",
        oauth_refresh_token="enc-active-refresh",
    )
    session.add_all([inactive_pinned, active_fallback])
    session.commit()
    session.refresh(inactive_pinned)
    session.refresh(active_fallback)
    pinned_id = inactive_pinned.id
    session.close()

    chatgpt_generate_mock = Mock(
        return_value={
            "subject": "Fallback Subject",
            "preheader": "Fallback Preheader",
            "body_markdown": "Fallback Body",
        }
    )
    monkeypatch.setattr(
        app.generation.openai_chatgpt,
        "generate",
        chatgpt_generate_mock,
    )

    newsletter = build_newsletter(
        provider_name="openai_chatgpt",
        api_key_id=pinned_id,
    )
    result = app.ai_generation.generate_newsletter_content(newsletter)

    assert result.status == "generated"
    assert result.subject == "Fallback Subject"
    chatgpt_generate_mock.assert_called_once()
    used_api_key = chatgpt_generate_mock.call_args.kwargs["api_key_row"]
    assert used_api_key.id == active_fallback.id


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
