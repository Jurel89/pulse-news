from __future__ import annotations

import hashlib
import hmac
import json
from importlib import reload

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PULSE_NEWS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PULSE_NEWS_SECRET_KEY", "test-secret")
    monkeypatch.setenv("PULSE_NEWS_ENVIRONMENT", "development")
    monkeypatch.setenv("PULSE_NEWS_RESEND_WEBHOOK_SECRET", "test-webhook-secret")

    import app.api.auth
    import app.api.newsletters
    import app.api.public
    import app.api.router
    import app.api.runs
    import app.api.webhooks
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
    reload(app.schemas)
    reload(app.auth)
    reload(app.api.auth)
    reload(app.api.newsletters)
    reload(app.api.public)
    reload(app.api.runs)
    reload(app.api.webhooks)
    reload(app.api.router)
    reload(app.main)
    app.database.init_database()

    with TestClient(app.main.app) as test_client:
        yield test_client


def make_signed_headers(secret: str, body: bytes, timestamp: str = "1712345678") -> dict[str, str]:
    signature = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{body.decode('utf-8')}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "content-type": "application/json",
        "resend-signature": signature,
        "resend-timestamp": timestamp,
    }


def create_newsletter_with_run(*, provider_id: str, email: str = "reader@example.com") -> int:
    import app.database
    from app.models import Newsletter, NewsletterRun

    session = app.database.get_session_maker()()
    try:
        newsletter = Newsletter(
            name="Webhook Brief",
            slug=f"webhook-brief-{provider_id}",
            description="Webhook processing test",
            prompt="Generate a delivery status test.",
            draft_subject="Webhook Brief",
            draft_preheader="Delivery event processing",
            draft_body_text="Delivery event body",
            provider_name="openai",
            model_name="gpt-4o-mini",
            template_key="signal",
            audience_name="ops",
            delivery_topic="webhook-brief",
            timezone="UTC",
            schedule_enabled=False,
            status="active",
        )
        session.add(newsletter)
        session.flush()
        session.add(
            NewsletterRun(
                newsletter_id=newsletter.id,
                trigger_mode="manual-send",
                run_status="sent",
                provider_name="openai",
                model_name="gpt-4o-mini",
                template_key="signal",
                recipient_count=1,
                snapshot_subject="Webhook Brief",
                snapshot_preheader="Delivery event processing",
                snapshot_body_text="Delivery event body",
                snapshot_recipient_emails=json.dumps([email]),
                delivery_outcomes=json.dumps(
                    [
                        {
                            "email": email,
                            "status": "sent",
                            "provider_id": provider_id,
                            "detail": "Sent through Resend",
                        }
                    ]
                ),
                result_mode="resend",
                result_message="Delivered to all active recipients through Resend.",
            )
        )
        session.commit()
        return newsletter.id
    finally:
        session.close()


def create_recipient(*, newsletter_id: int, email: str):
    import app.database
    from app.models import NewsletterRecipient

    session = app.database.get_session_maker()()
    try:
        recipient = NewsletterRecipient(
            newsletter_id=newsletter_id,
            email=email,
            is_active=True,
            status="subscribed",
            unsubscribe_token=f"token-{email}",
        )
        session.add(recipient)
        session.commit()
    finally:
        session.close()


def test_verify_resend_signature_accepts_valid_and_rejects_invalid_signatures(
    client: TestClient,
):
    import app.api.webhooks

    body = json.dumps({"type": "email.delivered", "data": {"email_id": "evt_123"}}).encode("utf-8")
    headers = make_signed_headers("test-webhook-secret", body)

    assert app.api.webhooks.verify_resend_signature(
        payload=body,
        signature=headers["resend-signature"],
        timestamp=headers["resend-timestamp"],
    )
    assert not app.api.webhooks.verify_resend_signature(
        payload=body,
        signature="invalid-signature",
        timestamp=headers["resend-timestamp"],
    )


def test_handle_resend_webhook_processes_delivery_events(client: TestClient):
    import app.database
    from app.models import NewsletterRunEvent

    provider_id = "email_delivery_123"
    create_newsletter_with_run(provider_id=provider_id, email="delivered@example.com")
    body = json.dumps(
        {
            "type": "email.delivered",
            "data": {"email_id": provider_id, "to": ["delivered@example.com"]},
        }
    ).encode("utf-8")

    response = client.post(
        "/api/webhooks/resend",
        content=body,
        headers=make_signed_headers("test-webhook-secret", body),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}

    session = app.database.get_session_maker()()
    try:
        event = session.scalar(
            select(NewsletterRunEvent).where(
                NewsletterRunEvent.provider_id == provider_id,
                NewsletterRunEvent.event_type == "webhook:email.delivered",
            )
        )
        assert event is not None
        assert event.event_status == "processed"
        assert event.message == json.dumps(
            {"type": "email.delivered", "email": ["delivered@example.com"]}
        )
    finally:
        session.close()


def test_handle_resend_webhook_suppresses_bounced_recipients(client: TestClient):
    import app.database
    from app.models import NewsletterRecipient, NewsletterRunEvent

    provider_id = "email_bounce_123"
    newsletter_id = create_newsletter_with_run(provider_id=provider_id, email="bounced@example.com")
    create_recipient(newsletter_id=newsletter_id, email="bounced@example.com")
    body = json.dumps(
        {
            "type": "email.bounced",
            "data": {"email_id": provider_id, "to": ["bounced@example.com"]},
        }
    ).encode("utf-8")

    response = client.post(
        "/api/webhooks/resend",
        content=body,
        headers=make_signed_headers("test-webhook-secret", body),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}

    session = app.database.get_session_maker()()
    try:
        recipient = session.scalar(
            select(NewsletterRecipient).where(NewsletterRecipient.email == "bounced@example.com")
        )
        assert recipient is not None
        assert recipient.is_active is False
        assert recipient.status == "suppressed_bounce"
        assert recipient.suppression_reason == "bounce"
        assert recipient.unsubscribed_at is not None

        event = session.scalar(
            select(NewsletterRunEvent).where(
                NewsletterRunEvent.provider_id == provider_id,
                NewsletterRunEvent.event_type == "webhook:email.bounced",
            )
        )
        assert event is not None
    finally:
        session.close()


def test_handle_resend_webhook_rejects_invalid_json_payload(client: TestClient):
    body = b"not-json"

    response = client.post(
        "/api/webhooks/resend",
        content=body,
        headers=make_signed_headers("test-webhook-secret", body),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid JSON payload."}
