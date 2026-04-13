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


def persist_operation_modes(*, ai_generation_mode="live", email_delivery_mode="live") -> None:
    import app.database
    from app.auth import get_or_create_system_settings

    session = app.database.get_session_maker()()
    try:
        settings = get_or_create_system_settings(session)
        settings.ai_generation_mode = ai_generation_mode
        settings.email_delivery_mode = email_delivery_mode
        session.add(settings)
        session.commit()
    finally:
        session.close()


def bootstrap_operator(client: TestClient) -> None:
    response = client.post(
        "/api/auth/bootstrap",
        json={"email": "operator@example.com", "password": "super-secret-password"},
    )
    assert response.status_code == 201


def test_get_resend_api_key_uses_newsletter_resend_key_instead_of_ai_key(client: TestClient):
    import app.database
    import app.email_delivery
    from app.models import ApiKey, Newsletter

    session = app.database.get_session_maker()()
    try:
        ai_key = ApiKey(
            name="OpenAI key",
            provider_type="openai",
            key_value="sk-ai-key",
            is_active=True,
        )
        resend_key = ApiKey(
            name="Resend key",
            provider_type="resend",
            key_value="re-newsletter-key",
            is_active=True,
        )
        session.add_all([ai_key, resend_key])
        session.flush()

        newsletter = Newsletter(
            name="Delivery Brief",
            slug="delivery-brief",
            description="Newsletter-specific resend key test",
            prompt="Generate a delivery brief.",
            draft_subject="Delivery Brief",
            draft_preheader="Delivery test",
            draft_body_text="Body copy",
            provider_name="openai",
            model_name="gpt-4o-mini",
            template_key="signal",
            api_key_id=ai_key.id,
            resend_api_key_id=resend_key.id,
            audience_name="ops",
            delivery_topic="delivery-brief",
            timezone="UTC",
            schedule_enabled=False,
            status="active",
        )
        session.add(newsletter)
        session.commit()
        session.refresh(newsletter)
    finally:
        session.close()

    settings = make_settings(resend_api_key="re-env-key")

    assert app.email_delivery._get_resend_api_key(settings, newsletter) == "re-newsletter-key"


def test_get_resend_api_key_returns_none_without_newsletter_selection_or_environment_key(
    client: TestClient,
):
    import app.database
    import app.email_delivery
    from app.models import ApiKey, Newsletter

    session = app.database.get_session_maker()()
    try:
        resend_key = ApiKey(
            name="Fallback Resend key",
            provider_type="resend",
            key_value="re-database-key",
            is_active=True,
        )
        session.add(resend_key)
        session.flush()

        newsletter = Newsletter(
            name="Delivery Brief",
            slug="delivery-brief-database-fallback",
            description="Database resend fallback test",
            prompt="Generate a delivery brief.",
            draft_subject="Delivery Brief",
            draft_preheader="Delivery test",
            draft_body_text="Body copy",
            provider_name="openai",
            model_name="gpt-4o-mini",
            template_key="signal",
            audience_name="ops",
            delivery_topic="delivery-brief",
            timezone="UTC",
            schedule_enabled=False,
            status="active",
        )
        session.add(newsletter)
        session.commit()
        session.refresh(newsletter)
    finally:
        session.close()

    settings = make_settings()

    assert app.email_delivery._get_resend_api_key(settings, newsletter) is None


def test_get_resend_api_key_uses_complete_environment_configuration_when_no_key_is_pinned(
    client: TestClient,
):
    import app.database
    import app.email_delivery
    from app.models import ApiKey, DeliveryProfile, Newsletter

    session = app.database.get_session_maker()()
    try:
        resend_key = ApiKey(
            name="Fallback Resend key",
            provider_type="resend",
            key_value="re-database-key",
            is_active=True,
        )
        session.add(resend_key)
        session.flush()

        newsletter = Newsletter(
            name="Delivery Brief",
            slug="delivery-brief-env-precedence",
            description="Environment resend precedence test",
            prompt="Generate a delivery brief.",
            draft_subject="Delivery Brief",
            draft_preheader="Delivery test",
            draft_body_text="Body copy",
            provider_name="openai",
            model_name="gpt-4o-mini",
            template_key="signal",
            audience_name="ops",
            delivery_topic="delivery-brief",
            timezone="UTC",
            schedule_enabled=False,
            status="active",
        )
        session.add(newsletter)
        session.flush()
        delivery_profile = DeliveryProfile(
            name="System Default Delivery",
            provider_type="resend",
            api_key_binding_mode="system_default",
        )
        session.add(delivery_profile)
        session.flush()
        newsletter.delivery_profile_id = delivery_profile.id
        session.commit()
        session.refresh(newsletter)
    finally:
        session.close()

    settings = make_settings(resend_api_key="re-env-key", resend_from_email="sender@example.com")

    assert app.email_delivery._get_resend_api_key(settings, newsletter) == "re-env-key"


def test_get_resend_api_key_requires_sender_email_without_falling_back_to_database_key(
    client: TestClient,
):
    import app.database
    import app.email_delivery
    from app.models import ApiKey, Newsletter

    session = app.database.get_session_maker()()
    try:
        resend_key = ApiKey(
            name="UI Resend key",
            provider_type="resend",
            key_value="re-database-key",
            from_email="newsletter@example.com",
            is_active=True,
        )
        session.add(resend_key)
        session.flush()

        newsletter = Newsletter(
            name="Delivery Brief",
            slug="delivery-brief-env-no-sender",
            description="Environment key without sender email fallback test",
            prompt="Generate a delivery brief.",
            draft_subject="Delivery Brief",
            draft_preheader="Delivery test",
            draft_body_text="Body copy",
            provider_name="openai",
            model_name="gpt-4o-mini",
            template_key="signal",
            audience_name="ops",
            delivery_topic="delivery-brief",
            timezone="UTC",
            schedule_enabled=False,
            status="active",
        )
        session.add(newsletter)
        session.commit()
        session.refresh(newsletter)
    finally:
        session.close()

    # Env API key set but no sender email — should fail closed instead of falling through.
    settings = make_settings(resend_api_key="re-env-key")

    assert app.email_delivery._get_resend_api_key(settings, newsletter) is None


def test_get_resend_api_key_fails_closed_without_pinned_key_or_system_default_profile(
    client: TestClient,
):
    import app.database
    import app.email_delivery
    from app.models import Newsletter

    session = app.database.get_session_maker()()
    try:
        newsletter = Newsletter(
            name="Delivery Brief",
            slug="delivery-brief-no-default",
            description="No resend default",
            prompt="Generate a delivery brief.",
            draft_subject="Delivery Brief",
            draft_preheader="Delivery test",
            draft_body_text="Body copy",
            provider_name="openai",
            model_name="gpt-4o-mini",
            template_key="signal",
            audience_name="ops",
            delivery_topic="delivery-brief",
            timezone="UTC",
            schedule_enabled=False,
            status="active",
        )
        session.add(newsletter)
        session.commit()
        session.refresh(newsletter)
    finally:
        session.close()

    settings = make_settings(resend_api_key="re-env-key", resend_from_email="sender@example.com")

    assert app.email_delivery._get_resend_api_key(settings, newsletter) is None


def test_send_test_email_returns_error_when_resend_is_not_configured_by_default(
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

    assert result.status == "error"
    assert result.mode == "none"
    assert result.provider_id is None
    assert result.to_email == "qa@example.com"
    assert "blocked" in result.message.lower()
    assert "switch email delivery mode to simulated in system settings" in result.message
    urlopen.assert_not_called()


def test_send_test_email_returns_explicit_local_preview_when_simulation_is_enabled(
    client: TestClient,
    monkeypatch,
):
    import app.email_delivery

    persist_operation_modes(email_delivery_mode="simulated")
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
    assert "Email delivery mode is set to simulated in system settings." in result.message
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

    with pytest.raises(
        RuntimeError,
        match='Resend test send failed\\..*Provider response: {"message":"invalid sender"}',
    ):
        app.email_delivery.send_test_email(
            settings=settings,
            rendered=rendered,
            to_email="qa@example.com",
        )

    urlopen.assert_called_once()


def test_send_test_email_fails_closed_when_pinned_key_is_inactive_even_if_environment_key_exists(
    client: TestClient,
    monkeypatch,
):
    import app.database
    import app.email_delivery
    from app.models import ApiKey, Newsletter

    session = app.database.get_session_maker()()
    try:
        resend_key = ApiKey(
            name="Inactive Resend key",
            provider_type="resend",
            key_value="re-newsletter-key",
            is_active=False,
        )
        session.add(resend_key)
        session.flush()

        newsletter = Newsletter(
            name="Delivery Brief",
            slug="delivery-brief-fallback",
            description="Environment fallback test",
            prompt="Generate a delivery brief.",
            draft_subject="Delivery Brief",
            draft_preheader="Delivery test",
            draft_body_text="Body copy",
            provider_name="openai",
            model_name="gpt-4o-mini",
            template_key="signal",
            resend_api_key_id=resend_key.id,
            audience_name="ops",
            delivery_topic="delivery-brief",
            timezone="UTC",
            schedule_enabled=False,
            status="active",
        )
        session.add(newsletter)
        session.commit()
        session.refresh(newsletter)
    finally:
        session.close()

    settings = make_settings(
        resend_api_key="re-env-key",
        resend_from_email="news@example.com",
    )

    urlopen = Mock()
    monkeypatch.setattr(app.email_delivery.request, "urlopen", urlopen)

    result = app.email_delivery.send_test_email(
        settings=settings,
        rendered=build_rendered_newsletter(),
        to_email="qa@example.com",
        newsletter=newsletter,
    )

    assert result.status == "error"
    assert result.mode == "none"
    assert "is inactive" in result.message
    assert "newsletter-specific Resend API key" in result.message
    assert "Using sender 'news@example.com'." in result.message
    urlopen.assert_not_called()


def test_send_test_email_reports_newsletter_key_decryption_failures(
    client: TestClient, monkeypatch
):
    import app.database
    import app.email_delivery
    from app.models import ApiKey, Newsletter

    session = app.database.get_session_maker()()
    try:
        resend_key = ApiKey(
            name="Broken Resend key",
            provider_type="resend",
            key_value="enc:v1:broken",
            is_active=True,
        )
        session.add(resend_key)
        session.flush()

        newsletter = Newsletter(
            name="Delivery Brief",
            slug="delivery-brief-broken-key",
            description="Broken resend key test",
            prompt="Generate a delivery brief.",
            draft_subject="Delivery Brief",
            draft_preheader="Delivery test",
            draft_body_text="Body copy",
            provider_name="openai",
            model_name="gpt-4o-mini",
            template_key="signal",
            resend_api_key_id=resend_key.id,
            audience_name="ops",
            delivery_topic="delivery-brief",
            timezone="UTC",
            schedule_enabled=False,
            status="active",
        )
        session.add(newsletter)
        session.commit()
        session.refresh(newsletter)
    finally:
        session.close()

    monkeypatch.setattr(
        app.email_delivery,
        "decrypt_secret",
        Mock(side_effect=ValueError("bad ciphertext")),
    )
    urlopen = Mock()
    monkeypatch.setattr(app.email_delivery.request, "urlopen", urlopen)

    result = app.email_delivery.send_test_email(
        settings=make_settings(),
        rendered=build_rendered_newsletter(),
        to_email="qa@example.com",
        newsletter=newsletter,
    )

    assert result.status == "error"
    assert result.mode == "none"
    assert "could not be decrypted" in result.message
    assert (
        "No sender email is configured for the selected newsletter-specific Resend key"
        in result.message
    )
    assert "switch email delivery mode to simulated in system settings" in result.message
    urlopen.assert_not_called()


def test_send_test_email_prefers_api_key_sender_email_over_environment_setting(
    client: TestClient,
    monkeypatch,
):
    import app.database
    import app.email_delivery
    from app.models import ApiKey, Newsletter

    session = app.database.get_session_maker()()
    try:
        resend_key = ApiKey(
            name="Newsletter Resend key",
            provider_type="resend",
            key_value="re-newsletter-key",
            from_email="key-sender@example.com",
            is_active=True,
        )
        session.add(resend_key)
        session.flush()

        newsletter = Newsletter(
            name="Delivery Brief",
            slug="delivery-brief-key-sender",
            description="Newsletter-specific sender test",
            prompt="Generate a delivery brief.",
            draft_subject="Delivery Brief",
            draft_preheader="Delivery test",
            draft_body_text="Body copy",
            provider_name="openai",
            model_name="gpt-4o-mini",
            template_key="signal",
            resend_api_key_id=resend_key.id,
            audience_name="ops",
            delivery_topic="delivery-brief",
            timezone="UTC",
            schedule_enabled=False,
            status="active",
        )
        session.add(newsletter)
        session.commit()
        session.refresh(newsletter)
    finally:
        session.close()

    settings = make_settings(
        resend_api_key="re-env-key",
        resend_from_email="env-sender@example.com",
    )

    class ResponseStub:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"id":"email_123"}'

    captured_request = {}

    def fake_urlopen(request_obj, timeout):
        captured_request["payload"] = __import__("json").loads(request_obj.data.decode("utf-8"))
        return ResponseStub()

    monkeypatch.setattr(app.email_delivery.request, "urlopen", fake_urlopen)

    result = app.email_delivery.send_test_email(
        settings=settings,
        rendered=build_rendered_newsletter(),
        to_email="qa@example.com",
        newsletter=newsletter,
    )

    assert result.status == "sent"
    assert captured_request["payload"]["from"] == "key-sender@example.com"
    assert "Using sender 'key-sender@example.com'." in result.message


def test_resend_api_key_test_reports_missing_sender_email(client: TestClient):
    bootstrap_operator(client)

    create_key_response = client.post(
        "/api/api-keys",
        json={
            "name": "Resend key",
            "provider_type": "resend",
            "key_value": "re-live-key",
            "is_active": True,
        },
    )
    assert create_key_response.status_code == 201
    api_key_id = create_key_response.json()["id"]

    provider_response = client.post(
        "/api/providers",
        json={
            "name": "Resend",
            "provider_type": "resend",
            "is_enabled": True,
            "default_model": "n/a",
        },
    )
    assert provider_response.status_code == 201

    test_response = client.post(f"/api/api-keys/{api_key_id}/test")

    assert test_response.status_code == 200
    payload = test_response.json()
    assert payload["status"] == "warning"
    assert "no sender email is configured" in payload["message"]


def test_resend_api_key_test_uses_api_key_sender_email(client: TestClient):
    bootstrap_operator(client)

    create_key_response = client.post(
        "/api/api-keys",
        json={
            "name": "Resend key",
            "provider_type": "resend",
            "key_value": "re-live-key",
            "from_email": "sender@example.com",
            "is_active": True,
        },
    )
    assert create_key_response.status_code == 201
    api_key_id = create_key_response.json()["id"]

    provider_response = client.post(
        "/api/providers",
        json={
            "name": "Resend",
            "provider_type": "resend",
            "is_enabled": True,
            "default_model": "n/a",
        },
    )
    assert provider_response.status_code == 201

    test_response = client.post(f"/api/api-keys/{api_key_id}/test")

    assert test_response.status_code == 200
    payload = test_response.json()
    assert payload["status"] == "ok"
    assert "sender@example.com" in payload["message"]


def test_newsletter_test_send_endpoint_returns_provider_error_detail(
    client: TestClient, monkeypatch
):
    import app.config
    import app.database
    import app.email_delivery
    from app.models import DeliveryProfile, DraftRevision, Newsletter

    bootstrap_operator(client)
    monkeypatch.setenv("PULSE_NEWS_RESEND_API_KEY", "re-env-key")
    monkeypatch.setenv("PULSE_NEWS_RESEND_FROM_EMAIL", "news@example.com")
    app.config.get_settings.cache_clear()

    session = app.database.get_session_maker()()
    try:
        newsletter = Newsletter(
            name="Delivery Brief",
            slug="delivery-brief-endpoint-error",
            description="Endpoint error detail test",
            prompt="Generate a delivery brief.",
            draft_subject="Delivery Brief",
            draft_preheader="Delivery test",
            draft_body_text="Body copy",
            provider_name="openai",
            model_name="gpt-4o-mini",
            template_key="signal",
            audience_name="ops",
            delivery_topic="delivery-brief",
            timezone="UTC",
            schedule_enabled=False,
            status="active",
        )
        session.add(newsletter)
        session.flush()
        revision = DraftRevision(
            newsletter_id=newsletter.id,
            version_number=1,
            state="approved",
            origin="imported",
            subject=newsletter.draft_subject,
            preheader=newsletter.draft_preheader,
            body_text=newsletter.draft_body_text,
            prompt_snapshot=newsletter.prompt,
        )
        session.add(revision)
        session.flush()
        newsletter.approved_revision_id = revision.id
        newsletter.draft_head_revision_id = revision.id
        delivery_profile = DeliveryProfile(
            name="System Default Delivery",
            provider_type="resend",
            api_key_binding_mode="system_default",
        )
        session.add(delivery_profile)
        session.flush()
        newsletter.delivery_profile_id = delivery_profile.id
        session.commit()
        newsletter_id = newsletter.id
        approved_revision_id = newsletter.approved_revision_id
    finally:
        session.close()

    http_error = HTTPError(
        url="https://api.resend.com/emails",
        code=422,
        msg="unprocessable entity",
        hdrs=None,
        fp=io.BytesIO(b'{"message":"invalid sender"}'),
    )
    monkeypatch.setattr(app.email_delivery.request, "urlopen", Mock(side_effect=http_error))

    response = client.post(
        f"/api/newsletters/{newsletter_id}/test-send",
        json={"to_email": "qa@example.com", "revision_id": approved_revision_id},
    )

    assert response.status_code == 502
    assert 'Provider response: {"message":"invalid sender"}' in response.json()["detail"]


def test_send_newsletter_email_returns_failed_outcomes_when_resend_is_not_configured_by_default(
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

    assert result.status == "failed"
    assert result.mode == "none"
    assert len(result.recipient_outcomes) == 2
    assert [outcome.email for outcome in result.recipient_outcomes] == [
        "first@example.com",
        "second@example.com",
    ]
    assert all(outcome.status == "failed" for outcome in result.recipient_outcomes)
    assert "switch email delivery mode to simulated in system settings" in result.message
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

    persist_operation_modes(email_delivery_mode="simulated")
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
    assert "Email delivery mode is set to simulated in system settings." in result.message
    assert (
        result.recipient_outcomes[0].detail
        == "Local preview simulation enabled in system settings."
    )


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
    assert sleep_calls[0] == 2


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
