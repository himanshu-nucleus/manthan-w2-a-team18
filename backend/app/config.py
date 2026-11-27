"""Application settings, loaded from environment variables or a local .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Values come from the environment, falling back to a local ``.env`` file.
    Never put real credentials in ``.env.example`` or in the repository.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "manthan-backend"
    environment: str = "local"
    log_level: str = "INFO"

    # Host port 5433, not 5432: some laptops already run a local PostgreSQL
    # service on 5432. Inside docker compose this is overridden to db:5432.
    database_url: str = "postgresql+psycopg://manthan:manthan@localhost:5433/manthan"

    # SQL echo is noisy; enable only while debugging a query.
    database_echo: bool = False

    api_prefix: str = "/api/v1"

    # Signs login tokens. The default is for local development only; set a
    # random SECRET_KEY in .env anywhere the app is shared.
    secret_key: str = "dev-only-insecure-secret-key-change-me"
    access_token_ttl_seconds: int = 8 * 60 * 60

    # Receipt files. A relative path resolves against the working directory
    # (backend/ locally, /app in the container, where it is a Docker volume).
    upload_dir: Path = Path("uploads")
    max_upload_bytes: int = 5 * 1024 * 1024
    max_attachments_per_claim: int = 10

    @property
    def is_local(self) -> bool:
        return self.environment.lower() in {"local", "dev", "development"}


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance.

    Cached so a single object is shared across the app. Tests that need
    different values should clear the cache: ``get_settings.cache_clear()``.
    """
    return Settings()
