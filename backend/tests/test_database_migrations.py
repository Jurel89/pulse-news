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
    assert {"api_keys", "email_templates", "providers"}.issubset(inspector.get_table_names())
    assert {"provider_id", "template_id", "api_key_id", "resend_api_key_id"}.issubset(
        {column["name"] for column in inspector.get_columns("newsletters")}
    )

    foreign_keys = {fk["name"]: fk for fk in inspector.get_foreign_keys("newsletters")}
    assert set(foreign_keys) >= {
        "fk_newsletters_provider_id",
        "fk_newsletters_template_id",
        "fk_newsletters_api_key_id",
        "fk_newsletters_resend_api_key_id",
    }
    assert foreign_keys["fk_newsletters_provider_id"]["referred_table"] == "providers"
    assert foreign_keys["fk_newsletters_template_id"]["referred_table"] == "email_templates"
    assert foreign_keys["fk_newsletters_api_key_id"]["referred_table"] == "api_keys"
    assert foreign_keys["fk_newsletters_resend_api_key_id"]["referred_table"] == "api_keys"

    with app.database.get_engine().connect() as connection:
        version = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert version == "1c2b6170f8d3"
