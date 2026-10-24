"""Application settings, loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "dev-insecure-secret-change-me"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/agentguard"
    # Used to derive the key that encrypts agent endpoint tokens at rest.
    secret_key: str = Field(default=INSECURE_DEFAULT_SECRET, min_length=16)

    allow_registration: bool = True
    session_ttl_hours: int = Field(default=12, ge=1, le=720)
    session_cookie_name: str = "ag_session"
    # Defaults to True outside development; override for plain-HTTP demos.
    cookie_secure: bool | None = None

    # Permit agent endpoints on private networks (e.g. a local agent in Docker).
    allow_private_agent_urls: bool = False
    login_rate_limit_per_minute: int = 10

    @model_validator(mode="after")
    def _check_production(self) -> Settings:
        if self.environment == "production" and self.secret_key == INSECURE_DEFAULT_SECRET:
            raise ValueError("SECRET_KEY must be set to a strong random value in production.")
        return self

    @property
    def secure_cookies(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
