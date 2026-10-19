from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str
    openai_api_key: str
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    admin_email: str = "admin@pizzaworld.com"
    admin_password: str = "admin123"
    chef_email: str = "chef@pizzaworld.com"
    chef_password: str = "chef123"

    borrow_threshold: float = 7000.0
    pay_later_days: int = 3
    llm_model: str = "gpt-4o-mini"
    cors_origins: str = "http://localhost:3000"

    @property
    def async_dsn(self) -> str:
        """Bare postgresql:// DSN from .env rewritten for psycopg."""
        url = self.database_url
        if url.startswith("postgresql+psycopg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        return url

    @property
    def sync_dsn(self) -> str:
        return self.async_dsn.replace("+psycopg", "", 1)

    @property
    def psycopg_dsn(self) -> str:
        """Bare libpq DSN (postgresql://...) for psycopg directly (checkpointer)."""
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
