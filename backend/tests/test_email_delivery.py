from __future__ import annotations

import io
from importlib import reload
from unittest.mock import Mock
from urllib.error import HTTPError

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
    import app.email_delivery
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
    reload(app.email_delivery)
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


def make_settings(**overrides):
    from app.config import Settings

    values = {
        "secret_key": "test-secret",
        "environment": "development",
    }
    values.update(overrides)
    return Settings(**values)


def build_rendered_newsletter():
    from app.email_templates import RenderedNewsletter

    return RenderedNewsletter(
        subject="Daily Brief",
        preheader="Top stories for operators",
        html="<!doctype html><html><body><p>Hello world</p></body></html>",
        plain_text="Daily Brief\n\nHello world",
        template_key="signal",
    )


def test_send_test_email_returns_local_preview_when_resend_is_not_configured(
    client: TestClient,
    monkeypatch,
):
    import app.email_delivery

    settings = make_settings()
    rendered = build_rendered_newsletter()
    urlopen = Mock()
    monkeypatch.setattr(app.email_delivery.request, "urlopen", urlopen)

    result = app.email_delivery.send_test_email(
        settings=settings,
        rendered=rendered,
        to_email="qa@example.com",
    )

    assert result.status == "simulated"
    assert result.mode == "local-preview"
    assert result.provider_id is None
    assert result.to_email == "qa@example.com"
    assert "preview-only" in result.message
    urlopen.assert_not_called()


def test_send_test_email_raises_runtime_error_when_resend_returns_http_error(
    client: TestClient,
    monkeypatch,
):
    import app.email_delivery

    settings = make_settings(
        resend_api_key="re_test_key",
        resend_from_email="news@example.com",
    )
    rendered = build_rendered_newsletter()
    http_error = HTTPError(
        url=settings.resend_api_url,
        code=422,
        msg="unprocessable entity",
        hdrs=None,
        fp=io.BytesIO(b'{"message":"invalid sender"}'),
    )
    urlopen = Mock(side_effect=http_error)
    monkeypatch.setattr(app.email_delivery.request, "urlopen", urlopen)

    with pytest.raises(RuntimeError, match='Resend test send failed: {"message":"invalid sender"}'):
        app.email_delivery.send_test_email(
            settings=settings,
            rendered=rendered,
            to_email="qa@example.com",
        )

    urlopen.assert_called_once()


def test_send_newsletter_email_returns_local_preview_outcomes_when_resend_is_not_configured(
    client: TestClient,
    monkeypatch,
):
    import app.email_delivery

    settings = make_settings()
    rendered = build_rendered_newsletter()
    urlopen = Mock()
    monkeypatch.setattr(app.email_delivery.request, "urlopen", urlopen)

    result = app.email_delivery.send_newsletter_email(
        settings=settings,
        rendered=rendered,
        recipient_targets=[
            app.email_delivery.RecipientDeliveryTarget(email="first@example.com"),
            app.email_delivery.RecipientDeliveryTarget(email="second@example.com"),
        ],
    )

    assert result.status == "fallback"
    assert result.mode == "local-preview"
    assert len(result.recipient_outcomes) == 2
    assert [outcome.email for outcome in result.recipient_outcomes] == [
        "first@example.com",
        "second@example.com",
    ]
    assert all(outcome.status == "simulated" for outcome in result.recipient_outcomes)
    urlopen.assert_not_called()


def test_send_newsletter_email_requires_resend_configuration_in_production(client: TestClient):
    import app.email_delivery

    settings = make_settings(environment="production")
    rendered = build_rendered_newsletter()

    with pytest.raises(RuntimeError, match="Cannot send emails in production"):
        app.email_delivery.send_newsletter_email(
            settings=settings,
            rendered=rendered,
            recipient_targets=[
                app.email_delivery.RecipientDeliveryTarget(email="operator@example.com")
            ],
        )


def test_build_unsubscribe_url_handles_missing_base_url_and_missing_tokens(
    client: TestClient,
    monkeypatch,
):
    import app.email_delivery

    monkeypatch.delenv("PULSE_NEWS_BASE_URL", raising=False)
    assert app.email_delivery._build_unsubscribe_url("token-123") is None

    monkeypatch.setenv("PULSE_NEWS_BASE_URL", "https://pulse.example.com/")
    assert app.email_delivery._build_unsubscribe_url("token-123") == (
        "https://pulse.example.com/api/public/unsubscribe/token-123"
    )
    assert app.email_delivery._build_unsubscribe_url(None) is None


def test_append_unsubscribe_footer_adds_html_and_plain_text_footers(client: TestClient):
    import app.email_delivery

    rendered = build_rendered_newsletter()
    html, plain_text = app.email_delivery._append_unsubscribe_footer(
        rendered=rendered,
        unsubscribe_url="https://pulse.example.com/api/public/unsubscribe/token-123",
    )

    assert 'href="https://pulse.example.com/api/public/unsubscribe/token-123"' in html
    assert "You are receiving this email because you subscribed to this newsletter." in html
    assert html.endswith("</html>")
    assert "---" in plain_text
    assert "Unsubscribe: https://pulse.example.com/api/public/unsubscribe/token-123" in plain_text


def test_send_newsletter_email_simulated_mode_returns_all_outcomes_for_large_batches(
    client: TestClient,
):
    import app.email_delivery

    settings = make_settings()
    rendered = build_rendered_newsletter()
    recipient_targets = [
        app.email_delivery.RecipientDeliveryTarget(email=f"user{index}@example.com")
        for index in range(120)
    ]

    result = app.email_delivery.send_newsletter_email(
        settings=settings,
        rendered=rendered,
        recipient_targets=recipient_targets,
    )

    assert result.status == "fallback"
    assert result.mode == "local-preview"
    assert len(result.recipient_outcomes) == 120
    assert result.recipient_outcomes[0].email == "user0@example.com"
    assert result.recipient_outcomes[-1].email == "user119@example.com"
    assert all(outcome.status == "simulated" for outcome in result.recipient_outcomes)
