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


def test_batch_sends_to_multiple_recipients_via_batch_endpoint(client: TestClient, monkeypatch):
    """When 2+ recipients, send_newsletter_email uses the batch endpoint."""
    import app.email_delivery

    settings = make_settings(
        resend_api_key="re_test_key",
        resend_from_email="news@example.com",
    )
    rendered = build_rendered_newsletter()
    targets = [
        app.email_delivery.RecipientDeliveryTarget(email="alice@example.com"),
        app.email_delivery.RecipientDeliveryTarget(email="bob@example.com"),
    ]

    batch_response = {
        "data": [{"id": "re_id_1"}, {"id": "re_id_2"}],
    }
    response_mock = Mock()
    response_mock.read.return_value = __import__("json").dumps(batch_response).encode()
    response_mock.__enter__ = Mock(return_value=response_mock)
    response_mock.__exit__ = Mock(return_value=False)

    urlopen = Mock(return_value=response_mock)
    monkeypatch.setattr(app.email_delivery.request, "urlopen", urlopen)
    monkeypatch.setattr(app.email_delivery.time, "sleep", Mock())

    result = app.email_delivery.send_newsletter_email(
        settings=settings,
        rendered=rendered,
        recipient_targets=targets,
        attempt_key="run-42",
    )

    assert result.status == "sent"
    assert result.mode == "resend"
    assert len(result.recipient_outcomes) == 2
    assert result.recipient_outcomes[0].email == "alice@example.com"
    assert result.recipient_outcomes[0].provider_id == "re_id_1"
    assert result.recipient_outcomes[1].email == "bob@example.com"
    assert result.recipient_outcomes[1].provider_id == "re_id_2"

    call_args = urlopen.call_args[0][0]
    assert "/emails/batch" in call_args.full_url
    assert call_args.get_header("Idempotency-key") == "run-42-chunk-1"
    assert call_args.get_header("X-batch-validation") == "permissive"


def test_batch_chunks_into_groups_of_100(client: TestClient, monkeypatch):
    """More than 100 recipients triggers multiple batch requests."""
    import app.email_delivery

    settings = make_settings(
        resend_api_key="re_test_key",
        resend_from_email="news@example.com",
    )
    rendered = build_rendered_newsletter()
    targets = [
        app.email_delivery.RecipientDeliveryTarget(email=f"user{i}@example.com") for i in range(150)
    ]

    batch_data_chunk1 = [{"id": f"id_{i}"} for i in range(100)]
    batch_data_chunk2 = [{"id": f"id_{i}"} for i in range(100, 150)]

    call_count = [0]

    def fake_urlopen(*args, **kwargs):
        call_count[0] += 1
        chunk_data = batch_data_chunk1 if call_count[0] == 1 else batch_data_chunk2
        r = Mock()
        r.read.return_value = __import__("json").dumps({"data": chunk_data}).encode()
        r.__enter__ = Mock(return_value=r)
        r.__exit__ = Mock(return_value=False)
        return r

    monkeypatch.setattr(app.email_delivery.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(app.email_delivery.time, "sleep", Mock())

    result = app.email_delivery.send_newsletter_email(
        settings=settings,
        rendered=rendered,
        recipient_targets=targets,
        attempt_key="run-99",
    )

    assert result.status == "sent"
    assert len(result.recipient_outcomes) == 150
    assert call_count[0] == 2


def test_batch_retry_on_429_then_success(client: TestClient, monkeypatch):
    """Batch request retries on 429 rate limit before succeeding."""
    import app.email_delivery

    settings = make_settings(
        resend_api_key="re_test_key",
        resend_from_email="news@example.com",
    )
    rendered = build_rendered_newsletter()
    targets = [
        app.email_delivery.RecipientDeliveryTarget(email="alice@example.com"),
        app.email_delivery.RecipientDeliveryTarget(email="bob@example.com"),
    ]

    rate_limit_error = HTTPError(
        url="https://api.resend.com/emails/batch",
        code=429,
        msg="Too Many Requests",
        hdrs=None,
        fp=io.BytesIO(b'{"message":"rate limit exceeded"}'),
    )

    success_response = {
        "data": [{"id": "re_id_1"}, {"id": "re_id_2"}],
    }

    call_count = [0]
    sleep_calls = []

    def fake_urlopen(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise rate_limit_error
        r = Mock()
        r.read.return_value = __import__("json").dumps(success_response).encode()
        r.__enter__ = Mock(return_value=r)
        r.__exit__ = Mock(return_value=False)
        return r

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(app.email_delivery.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(app.email_delivery.time, "sleep", fake_sleep)

    result = app.email_delivery.send_newsletter_email(
        settings=settings,
        rendered=rendered,
        recipient_targets=targets,
    )

    assert result.status == "sent"
    assert call_count[0] == 2
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 1


def test_batch_exhausts_retries_on_persistent_429(client: TestClient, monkeypatch):
    """After 3 attempts of 429, the final attempt returns the HTTP error."""
    import app.email_delivery

    settings = make_settings(
        resend_api_key="re_test_key",
        resend_from_email="news@example.com",
    )
    rendered = build_rendered_newsletter()
    targets = [
        app.email_delivery.RecipientDeliveryTarget(email="alice@example.com"),
        app.email_delivery.RecipientDeliveryTarget(email="bob@example.com"),
    ]

    rate_limit_error = HTTPError(
        url="https://api.resend.com/emails/batch",
        code=429,
        msg="Too Many Requests",
        hdrs=None,
        fp=io.BytesIO(b'{"message":"rate limit exceeded"}'),
    )

    sleep_calls = []
    monkeypatch.setattr(app.email_delivery.request, "urlopen", Mock(side_effect=rate_limit_error))
    monkeypatch.setattr(app.email_delivery.time, "sleep", lambda s: sleep_calls.append(s))

    result = app.email_delivery.send_newsletter_email(
        settings=settings,
        rendered=rendered,
        recipient_targets=targets,
    )

    assert result.status == "failed"
    assert len(sleep_calls) == 2
    assert "Resend HTTP error" in result.recipient_outcomes[0].detail


def test_batch_maps_partial_errors_from_permissive_response(client: TestClient, monkeypatch):
    """When permissive mode returns partial errors, failures are mapped correctly."""
    import app.email_delivery

    settings = make_settings(
        resend_api_key="re_test_key",
        resend_from_email="news@example.com",
    )
    rendered = build_rendered_newsletter()
    targets = [
        app.email_delivery.RecipientDeliveryTarget(email="alice@example.com"),
        app.email_delivery.RecipientDeliveryTarget(email="bob@example.com"),
        app.email_delivery.RecipientDeliveryTarget(email="charlie@example.com"),
    ]

    batch_response = {
        "data": [{"id": "re_alice"}, {"id": "re_charlie"}],
        "errors": [{"index": 1, "message": "invalid email address"}],
    }

    response_mock = Mock()
    response_mock.read.return_value = __import__("json").dumps(batch_response).encode()
    response_mock.__enter__ = Mock(return_value=response_mock)
    response_mock.__exit__ = Mock(return_value=False)

    monkeypatch.setattr(app.email_delivery.request, "urlopen", Mock(return_value=response_mock))
    monkeypatch.setattr(app.email_delivery.time, "sleep", Mock())

    result = app.email_delivery.send_newsletter_email(
        settings=settings,
        rendered=rendered,
        recipient_targets=targets,
    )

    assert result.status == "partial"
    outcomes = result.recipient_outcomes
    assert len(outcomes) == 3

    assert outcomes[0].email == "alice@example.com"
    assert outcomes[0].status == "sent"
    assert outcomes[0].provider_id == "re_alice"

    assert outcomes[1].email == "bob@example.com"
    assert outcomes[1].status == "failed"
    assert "invalid email address" in outcomes[1].detail

    assert outcomes[2].email == "charlie@example.com"
    assert outcomes[2].status == "sent"
    assert outcomes[2].provider_id == "re_charlie"


def test_batch_handles_non_429_http_error_without_retry(client: TestClient, monkeypatch):
    """Non-429 HTTP errors fail immediately without retrying."""
    import app.email_delivery

    settings = make_settings(
        resend_api_key="re_test_key",
        resend_from_email="news@example.com",
    )
    rendered = build_rendered_newsletter()
    targets = [
        app.email_delivery.RecipientDeliveryTarget(email="alice@example.com"),
        app.email_delivery.RecipientDeliveryTarget(email="bob@example.com"),
    ]

    server_error = HTTPError(
        url="https://api.resend.com/emails/batch",
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=io.BytesIO(b'{"message":"internal error"}'),
    )

    urlopen = Mock(side_effect=server_error)
    monkeypatch.setattr(app.email_delivery.request, "urlopen", urlopen)
    monkeypatch.setattr(app.email_delivery.time, "sleep", Mock())

    result = app.email_delivery.send_newsletter_email(
        settings=settings,
        rendered=rendered,
        recipient_targets=targets,
    )

    assert result.status == "failed"
    assert urlopen.call_count == 1
    assert "Resend HTTP error" in result.recipient_outcomes[0].detail


def test_map_batch_response_handles_non_dict_response(client: TestClient):
    """Non-dict batch response returns all failures."""
    import app.email_delivery

    targets = [app.email_delivery.RecipientDeliveryTarget(email="a@b.com")]
    outcomes = app.email_delivery._map_batch_response_to_outcomes(
        recipient_targets=targets,
        response_payload="not a dict",
    )

    assert len(outcomes) == 1
    assert outcomes[0].status == "failed"
    assert "not a JSON object" in outcomes[0].detail


def test_single_recipient_uses_single_send_path(client: TestClient, monkeypatch):
    """With exactly 1 recipient, the single-send path is used (not batch)."""
    import app.email_delivery

    settings = make_settings(
        resend_api_key="re_test_key",
        resend_from_email="news@example.com",
    )
    rendered = build_rendered_newsletter()
    targets = [app.email_delivery.RecipientDeliveryTarget(email="solo@example.com")]

    response_mock = Mock()
    response_mock.read.return_value = __import__("json").dumps({"id": "re_solo"}).encode()
    response_mock.__enter__ = Mock(return_value=response_mock)
    response_mock.__exit__ = Mock(return_value=False)

    urlopen = Mock(return_value=response_mock)
    monkeypatch.setattr(app.email_delivery.request, "urlopen", urlopen)

    result = app.email_delivery.send_newsletter_email(
        settings=settings,
        rendered=rendered,
        recipient_targets=targets,
    )

    assert result.status == "sent"
    assert len(result.recipient_outcomes) == 1
    assert result.recipient_outcomes[0].provider_id == "re_solo"
    call_args = urlopen.call_args[0][0]
    assert "/emails/batch" not in call_args.full_url
