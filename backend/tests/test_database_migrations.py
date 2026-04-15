from __future__ import annotations

from importlib import reload

import sqlalchemy as sa


def test_init_database_applies_sqlite_safe_relationship_migration(tmp_path, monkeypatch):
    monkeypatch.setenv("PULSE_NEWS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PULSE_NEWS_SECRET_KEY", "test-secret")
    monkeypatch.setenv("PULSE_NEWS_ENVIRONMENT", "development")

    import app.config
    import app.database
    import app.models

    app.config.get_settings.cache_clear()
    app.database.get_engine.cache_clear()
    app.database.get_session_maker.cache_clear()

    reload(app.config)
    reload(app.database)
    reload(app.models)

    app.database.init_database()

    settings = app.config.get_settings()
    database_path = settings.data_dir / "pulse_news.db"
    inspector = sa.inspect(app.database.get_engine())

    assert database_path.exists()
    table_names = set(inspector.get_table_names())

    assert {
        "users",
        "system_settings",
        "email_templates",
        "providers",
        "api_keys",
        "newsletters",
        "newsletter_recipients",
        "newsletter_runs",
        "newsletter_run_events",
        "audit_events",
        "alembic_version",
    }.issubset(table_names)
    assert "draft_revisions" not in table_names
    assert "generation_profiles" not in table_names
    assert "delivery_profiles" not in table_names
    assert "from_email" in {column["name"] for column in inspector.get_columns("api_keys")}
    newsletter_columns = {column["name"] for column in inspector.get_columns("newsletters")}
    assert {
        "provider_id",
        "template_id",
        "api_key_id",
        "resend_api_key_id",
        "from_email",
    }.issubset(newsletter_columns)
    assert "approved_revision_id" not in newsletter_columns
    assert "draft_head_revision_id" not in newsletter_columns
    assert "generation_profile_id" not in newsletter_columns
    assert "delivery_profile_id" not in newsletter_columns
    assert "version" not in newsletter_columns
    assert "subject" in newsletter_columns
    assert "preheader" in newsletter_columns
    assert "body_text" in newsletter_columns
    assert "draft_subject" not in newsletter_columns
    assert "draft_preheader" not in newsletter_columns
    assert "draft_body_text" not in newsletter_columns

    newsletter_run_columns = {column["name"] for column in inspector.get_columns("newsletter_runs")}
    assert "run_type" in newsletter_run_columns
    assert "revision_id" not in newsletter_run_columns

    foreign_keys = {fk["name"]: fk for fk in inspector.get_foreign_keys("newsletters")}
    assert set(foreign_keys) >= {
        "fk_newsletters_provider_id",
        "fk_newsletters_template_id",
        "fk_newsletters_api_key_id",
        "fk_newsletters_resend_api_key_id",
    }
    assert "fk_newsletters_approved_revision_id" not in foreign_keys
    assert "fk_newsletters_draft_head_revision_id" not in foreign_keys
    assert "fk_newsletters_generation_profile_id" not in foreign_keys
    assert "fk_newsletters_delivery_profile_id" not in foreign_keys
    assert foreign_keys["fk_newsletters_provider_id"]["referred_table"] == "providers"
    assert foreign_keys["fk_newsletters_template_id"]["referred_table"] == "email_templates"
    assert foreign_keys["fk_newsletters_api_key_id"]["referred_table"] == "api_keys"
    assert foreign_keys["fk_newsletters_resend_api_key_id"]["referred_table"] == "api_keys"

    with app.database.get_engine().connect() as connection:
        version = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert version == "c14d9e5f6a7b"
