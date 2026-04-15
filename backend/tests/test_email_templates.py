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
        "subject": "Template Brief",
        "preheader": "Signals and notes for operators",
        "body_text": "Line one\n\nLine two",
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
        "\n\n---\nSent from Pulse-News — https://github.com/Jurel89/pulse-news"
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
            subject="Ops & Markets",
            preheader="Signals <and> notes",
            body_text="First <line>\n\nSecond & final",
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


def test_footer_present_in_html(client: TestClient):
    import app.email_templates

    rendered = app.email_templates.render_newsletter(build_newsletter())
    assert "Pulse-News" in rendered.html
    assert "https://github.com/Jurel89/pulse-news" in rendered.html
    assert "Pulse-News" in rendered.plain_text


def test_markdown_headings_rendered(client: TestClient):
    import app.email_templates

    rendered = app.email_templates.render_newsletter(
        build_newsletter(body_text="## Section Title\n\nParagraph text")
    )
    assert "<h2" in rendered.html
    assert "Section Title</h2>" in rendered.html
    assert "<p" in rendered.html
    assert "Paragraph text</p>" in rendered.html


def test_markdown_bold_and_italic(client: TestClient):
    import app.email_templates

    rendered = app.email_templates.render_newsletter(
        build_newsletter(body_text="This is **bold** and *italic* text.")
    )
    assert "<strong>bold</strong>" in rendered.html
    assert "<em>italic</em>" in rendered.html


def test_markdown_bullet_list(client: TestClient):
    import app.email_templates

    rendered = app.email_templates.render_newsletter(
        build_newsletter(body_text="- Item one\n- Item two\n- Item three")
    )
    assert "<ul" in rendered.html
    assert "<li" in rendered.html
    assert "Item one</li>" in rendered.html
    assert "Item three</li>" in rendered.html


def test_markdown_code_and_links(client: TestClient):
    import app.email_templates

    rendered = app.email_templates.render_newsletter(
        build_newsletter(body_text="Use `pip install` and visit [docs](https://example.com).")
    )
    assert "<code" in rendered.html
    assert "pip install</code>" in rendered.html
    assert 'href="https://example.com"' in rendered.html


def test_plain_text_not_treated_as_heading(client: TestClient):
    import app.email_templates

    rendered = app.email_templates.render_newsletter(
        build_newsletter(body_text="This has **bold** in the middle of text.")
    )
    assert "<h2" not in rendered.html
    assert "<strong>bold</strong>" in rendered.html


def test_standalone_bold_line_is_heading(client: TestClient):
    import app.email_templates

    rendered = app.email_templates.render_newsletter(
        build_newsletter(body_text="**Major Releases**\n\nSome content here.")
    )
    assert "<h2" in rendered.html
    assert "Major Releases</h2>" in rendered.html


def test_custom_template_with_body_tag_gets_footer(client: TestClient):
    import app.email_templates

    template = (
        "<!doctype html><html><body><h1>{{subject}}</h1><div>{{body_html}}</div></body></html>"
    )
    rendered = app.email_templates.render_custom_template(
        template, "Test Subject", "pre", "<p>Hello</p>", "My Newsletter"
    )
    assert "Pulse-News" in rendered
    assert "https://github.com/Jurel89/pulse-news" in rendered


def test_custom_template_with_footer_placeholder_gets_footer(client: TestClient):
    import app.email_templates

    template = "<html><body><h1>{{subject}}</h1>{{body_html}}{{footer}}</body></html>"
    rendered = app.email_templates.render_custom_template(
        template, "Test Subject", "pre", "<p>Hello</p>", "My Newsletter"
    )
    assert "Pulse-News" in rendered
    assert rendered.count("Pulse-News") == 1


def test_custom_template_without_body_or_footer_still_gets_footer(client: TestClient):
    import app.email_templates

    template = "<html><h1>{{subject}}</h1><div>{{body_html}}</div></html>"
    rendered = app.email_templates.render_custom_template(
        template, "Test Subject", "pre", "<p>Hello</p>", "My Newsletter"
    )
    assert "Pulse-News" in rendered
