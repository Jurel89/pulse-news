from __future__ import annotations

from sqlalchemy import select
from test_newsletters import (
    bootstrap_operator,
    create_test_api_key,
    create_test_provider,
)
from test_newsletters import (
    client as client,
)

from app.models import DeliveryProfile, GenerationProfile, Newsletter
from app.profile_service import resolve_delivery_profile, resolve_generation_profile


def test_profile_service_resolves_generation_and_delivery_profiles(client):
    bootstrap_operator(client)
    provider_id = create_test_provider(client, "openai")
    generation_api_key_id = create_test_api_key(client, "openai")
    resend_api_key_id = create_test_api_key(client, "resend")

    create_response = client.post(
        "/api/newsletters",
        json={
            "name": "Profile Test",
            "description": "Testing profiles",
            "prompt": "Test profile resolution.",
            "draft_subject": "Profile subject",
            "draft_preheader": "Profile preheader",
            "draft_body_text": "Profile body",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "operators",
            "delivery_topic": "profile-test",
            "timezone": "UTC",
            "schedule_enabled": False,
            "status": "active",
            "recipient_import_text": "qa@example.com",
        },
    )
    assert create_response.status_code == 201
    newsletter_id = create_response.json()["id"]

    import app.database

    session = app.database.get_session_maker()()
    try:
        newsletter = session.scalar(select(Newsletter).where(Newsletter.id == newsletter_id))
        assert newsletter is not None

        generation_profile = GenerationProfile(
            name="Weekly OpenAI",
            provider_id=provider_id,
            model_name="gpt-4.1-mini",
            api_key_binding_mode="pinned_key",
            api_key_id=generation_api_key_id,
        )
        delivery_profile = DeliveryProfile(
            name="Ops Delivery",
            provider_type="resend",
            api_key_binding_mode="pinned_key",
            api_key_id=resend_api_key_id,
            from_email="ops@example.com",
        )
        session.add_all([generation_profile, delivery_profile])
        session.flush()

        newsletter.generation_profile_id = generation_profile.id
        newsletter.delivery_profile_id = delivery_profile.id
        session.add(newsletter)
        session.commit()
        session.refresh(newsletter)

        generation_resolution = resolve_generation_profile(session, newsletter)
        delivery_resolution = resolve_delivery_profile(session, newsletter)

        assert generation_resolution.profile is not None
        assert generation_resolution.api_key_id == generation_api_key_id
        assert generation_resolution.model_name == "gpt-4.1-mini"
        assert delivery_resolution.profile is not None
        assert delivery_resolution.api_key_id == resend_api_key_id
        assert delivery_resolution.from_email == "ops@example.com"
    finally:
        session.close()
