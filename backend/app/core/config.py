"""Backend settings (pydantic-settings) — env-driven, sensible dev defaults.

The heavy ML/retrieval configuration stays in the platform's ``config/platform.yaml``
(loaded by ``ala.config.load_settings``); this only holds the web concerns (DB,
Redis, JWT, CORS). Switching the database or LLM model is a config/env change —
zero code.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DIGILER_", env_file=".env", extra="ignore")

    env: str = "development"
    project_name: str = "Digiler AI"
    api_prefix: str = "/api"

    cors_origins: str = "http://localhost:3000"
    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    database_url: str = "sqlite+aiosqlite:///./digiler.db"
    redis_url: str = "redis://localhost:6379/0"

    upload_dir: str = "./uploads"
    max_upload_mb: int = 200
    rate_limit_per_minute: int = 120

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
