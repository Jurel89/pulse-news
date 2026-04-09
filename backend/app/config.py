from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Pulse News"
    environment: str = "development"
    secret_key: str = Field(
        default="change-me-before-production",
        description="Session signing key for the single-user admin app.",
    )
    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    frontend_dist_dir: Path = Field(default=PROJECT_ROOT / "frontend" / "dist")
    database_path: Path | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_prefix="PULSE_NEWS_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        database_path = self.database_path or self.data_dir / "pulse_news.db"
        return f"sqlite:///{database_path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
