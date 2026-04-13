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
    assert {
        "api_keys",
        "delivery_profiles",
        "draft_revisions",
        "email_templates",
        "generation_profiles",
        "providers",
    }.issubset(inspector.get_table_names())
    assert "from_email" in {column["name"] for column in inspector.get_columns("api_keys")}
    assert {
        "provider_id",
        "template_id",
        "api_key_id",
        "resend_api_key_id",
        "approved_revision_id",
        "draft_head_revision_id",
        "generation_profile_id",
        "delivery_profile_id",
        "version",
    }.issubset({column["name"] for column in inspector.get_columns("newsletters")})
    assert {"revision_id", "run_type"}.issubset(
        {column["name"] for column in inspector.get_columns("newsletter_runs")}
    )
    assert "source_bundle_snapshot_json" in {
        column["name"] for column in inspector.get_columns("draft_revisions")
    }
    assert "created_by_email" in {
        column["name"] for column in inspector.get_columns("draft_revisions")
    }

    foreign_keys = {fk["name"]: fk for fk in inspector.get_foreign_keys("newsletters")}
    assert set(foreign_keys) >= {
        "fk_newsletters_provider_id",
        "fk_newsletters_template_id",
        "fk_newsletters_api_key_id",
        "fk_newsletters_resend_api_key_id",
        "fk_newsletters_approved_revision_id",
        "fk_newsletters_draft_head_revision_id",
        "fk_newsletters_generation_profile_id",
        "fk_newsletters_delivery_profile_id",
    }
    assert foreign_keys["fk_newsletters_provider_id"]["referred_table"] == "providers"
    assert foreign_keys["fk_newsletters_template_id"]["referred_table"] == "email_templates"
    assert foreign_keys["fk_newsletters_api_key_id"]["referred_table"] == "api_keys"
    assert foreign_keys["fk_newsletters_resend_api_key_id"]["referred_table"] == "api_keys"
    assert (
        foreign_keys["fk_newsletters_approved_revision_id"]["referred_table"] == "draft_revisions"
    )
    assert (
        foreign_keys["fk_newsletters_draft_head_revision_id"]["referred_table"] == "draft_revisions"
    )
    assert (
        foreign_keys["fk_newsletters_generation_profile_id"]["referred_table"]
        == "generation_profiles"
    )
    assert (
        foreign_keys["fk_newsletters_delivery_profile_id"]["referred_table"] == "delivery_profiles"
    )

    with app.database.get_engine().connect() as connection:
        version = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert version == "9b0c1d2e3f4a"
