from __future__ import annotations

from importlib import reload

import pytest
from fastapi.testclient import TestClient


def create_test_api_key(client: TestClient, provider_type: str = "openai") -> int:
    response = client.post(
        "/api/api-keys",
        json={
            "name": f"Test {provider_type} Key",
            "provider_type": provider_type,
            "key_value": f"sk-test-{provider_type}-key-12345",
            "is_active": True,
        },
    )
    assert response.status_code == 201, f"Failed to create API key: {response.text}"
    return response.json()["id"]


def create_test_provider(
    client: TestClient, provider_type: str = "openai", is_enabled: bool = True
) -> int:
    create_test_api_key(client, provider_type)

    response = client.post(
        "/api/providers",
        json={
            "name": f"Test {provider_type.title()}",
            "provider_type": provider_type,
            "is_enabled": is_enabled,
            "default_model": "gpt-4o-mini",
        },
    )
    assert response.status_code == 201, f"Failed to create provider: {response.text}"
    return response.json()["id"]


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


def bootstrap_operator(client: TestClient) -> None:
    response = client.post(
        "/api/auth/bootstrap",
        json={
            "email": "operator@example.com",
            "password": "super-secret-password",
        },
    )
    assert response.status_code == 201


def test_provider_presets_endpoint_returns_presets(client: TestClient):
    bootstrap_operator(client)

    response = client.get("/api/providers/presets/list")
    assert response.status_code == 200
    presets = response.json()
    assert isinstance(presets, list)
    assert len(presets) >= 4
    keys = {p["key"] for p in presets}
    assert "openai" in keys
    assert "anthropic" in keys
    assert "zai" in keys
    assert "kimi" in keys
    for preset in presets:
        assert "key" in preset
        assert "name" in preset
        assert "adapter" in preset
        assert "recommended_models" in preset


def test_provider_toggle_preserves_configuration(client: TestClient):
    bootstrap_operator(client)

    provider_id = create_test_provider(client, "openai", is_enabled=True)

    get_response = client.get(f"/api/providers/{provider_id}")
    assert get_response.status_code == 200
    config = get_response.json()["configuration"]
    assert config == "{}" or config is None

    toggle_response = client.put(
        f"/api/providers/{provider_id}",
        json={
            "name": "Test OpenAI",
            "provider_type": "openai",
            "is_enabled": False,
        },
    )
    assert toggle_response.status_code == 200
    assert toggle_response.json()["is_enabled"] is False
    config = toggle_response.json()["configuration"]
    assert config == "{}" or config is None


def test_template_deletion_blocked_when_referenced_by_newsletter(client: TestClient):
    bootstrap_operator(client)

    template_response = client.post(
        "/api/email-templates",
        json={
            "name": "Custom Template",
            "key": "custom-test",
            "description": "Test template for deletion guard",
            "html_template": "<html><body>{{content}}</body></html>",
            "is_default": False,
        },
    )
    assert template_response.status_code == 201
    template_id = template_response.json()["id"]

    create_test_provider(client, "openai")

    client.post(
        "/api/newsletters",
        json={
            "name": "Template Guard Test",
            "description": "Uses custom template",
            "prompt": "Test",
            "draft_subject": "Subject",
            "draft_preheader": "Pre",
            "draft_body_text": "Body",
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "custom-test",
            "audience_name": "test",
            "delivery_topic": "test",
            "timezone": "UTC",
            "schedule_enabled": False,
            "status": "draft",
            "recipient_import_text": "test@example.com",
        },
    )

    delete_response = client.delete(f"/api/email-templates/{template_id}")
    assert delete_response.status_code == 409
    assert "referenced by newsletters" in delete_response.json()["detail"].lower()


def test_newsletter_validation_rejects_unknown_provider_type(client: TestClient):
    bootstrap_operator(client)

    response = client.post(
        "/api/newsletters",
        json={
            "name": "Bad Provider",
            "description": "Uses fake provider",
            "prompt": "Test",
            "draft_subject": "Subject",
            "draft_preheader": "Pre",
            "draft_body_text": "Body",
            "provider_name": "totally-fake-provider-xyz",
            "model_name": "fake-model",
            "template_key": "signal",
            "audience_name": "test",
            "delivery_topic": "test",
            "timezone": "UTC",
            "schedule_enabled": False,
            "status": "draft",
            "recipient_import_text": "test@example.com",
        },
    )
    assert response.status_code == 422


def test_newsletter_validation_rejects_disabled_provider(client: TestClient):
    bootstrap_operator(client)

    create_test_api_key(client, "openai")
    provider_response = client.post(
        "/api/providers",
        json={
            "name": "Disabled Provider",
            "provider_type": "openai",
            "is_enabled": False,
            "default_model": "gpt-4o-mini",
        },
    )
    assert provider_response.status_code == 201
    provider_id = provider_response.json()["id"]

    response = client.post(
        "/api/newsletters",
        json={
            "name": "Disabled Provider Test",
            "description": "Should be rejected",
            "prompt": "Test",
            "draft_subject": "Subject",
            "draft_preheader": "Pre",
            "draft_body_text": "Body",
            "provider_id": provider_id,
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "template_key": "signal",
            "audience_name": "test",
            "delivery_topic": "test",
            "timezone": "UTC",
            "schedule_enabled": False,
            "status": "draft",
            "recipient_import_text": "test@example.com",
        },
    )
    assert response.status_code == 422
    assert "disabled" in response.json()["detail"].lower()


def test_newsletter_validation_rejects_model_not_in_catalog(client: TestClient):
    bootstrap_operator(client)

    provider_id = create_test_provider(client, "openai", is_enabled=True)

    response = client.post(
        "/api/newsletters",
        json={
            "name": "Bad Model Test",
            "description": "Should be rejected",
            "prompt": "Test",
            "draft_subject": "Subject",
            "draft_preheader": "Pre",
            "draft_body_text": "Body",
            "provider_id": provider_id,
            "provider_name": "openai",
            "model_name": "nonexistent-model-xyz-999",
            "template_key": "signal",
            "audience_name": "test",
            "delivery_topic": "test",
            "timezone": "UTC",
            "schedule_enabled": False,
            "status": "draft",
            "recipient_import_text": "test@example.com",
        },
    )
    assert response.status_code == 422
    assert "not enabled for provider" in response.json()["detail"].lower()


def test_newsletter_validation_rejects_mismatched_api_key_type(client: TestClient):
    bootstrap_operator(client)

    provider_id = create_test_provider(client, "openai", is_enabled=True)

    key_response = client.post(
        "/api/api-keys",
        json={
            "name": "Anthropic Key",
            "provider_type": "anthropic",
            "key_value": "sk-ant-fake-key-12345",
            "is_active": True,
        },
    )
    assert key_response.status_code == 201
    key_id = key_response.json()["id"]

    response = client.post(
        "/api/newsletters",
        json={
            "name": "Key Mismatch Test",
            "description": "Should be rejected",
            "prompt": "Test",
            "draft_subject": "Subject",
            "draft_preheader": "Pre",
            "draft_body_text": "Body",
            "provider_id": provider_id,
            "provider_name": "openai",
            "model_name": "gpt-4o-mini",
            "api_key_id": key_id,
            "template_key": "signal",
            "audience_name": "test",
            "delivery_topic": "test",
            "timezone": "UTC",
            "schedule_enabled": False,
            "status": "draft",
            "recipient_import_text": "test@example.com",
        },
    )
    assert response.status_code == 422
    assert "does not match" in response.json()["detail"].lower()


def test_api_key_secret_not_stored_in_plaintext(client: TestClient):
    from app.database import get_session_maker
    from app.models import ApiKey

    bootstrap_operator(client)

    create_response = client.post(
        "/api/api-keys",
        json={
            "name": "Secret Test Key",
            "provider_type": "openai",
            "key_value": "sk-test-secret-key-abc123xyz",
            "is_active": True,
        },
    )
    assert create_response.status_code == 201
    key_id = create_response.json()["id"]

    session = get_session_maker()()
    raw_key = session.get(ApiKey, key_id)
    assert raw_key is not None
    raw_value = raw_key.key_value
    session.close()

    assert raw_value != "sk-test-secret-key-abc123xyz", "Secret must be encrypted at rest"
    assert raw_value.startswith("enc:"), "Encrypted values must have enc: prefix"


def test_api_key_create_and_update_supports_from_email(client: TestClient):
    bootstrap_operator(client)

    create_response = client.post(
        "/api/api-keys",
        json={
            "name": "Resend Key",
            "provider_type": "resend",
            "key_value": "re-test-key",
            "from_email": "  sender@example.com  ",
            "is_active": True,
        },
    )
    assert create_response.status_code == 201
    created_payload = create_response.json()
    assert created_payload["from_email"] == "sender@example.com"

    api_key_id = created_payload["id"]
    update_response = client.put(
        f"/api/api-keys/{api_key_id}",
        json={
            "name": "Resend Key",
            "provider_type": "resend",
            "key_value": "re-test-key-updated",
            "from_email": "",
            "is_active": True,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["from_email"] is None


def test_api_key_create_rejects_invalid_from_email(client: TestClient):
    bootstrap_operator(client)

    response = client.post(
        "/api/api-keys",
        json={
            "name": "Resend Key",
            "provider_type": "resend",
            "key_value": "re-test-key",
            "from_email": "not-an-email",
            "is_active": True,
        },
    )

    assert response.status_code == 422
    assert "from_email" in response.text
