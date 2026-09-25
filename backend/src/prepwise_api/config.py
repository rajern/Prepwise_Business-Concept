from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    applicationinsights_connection_string: str | None = None
    otel_service_name: str = "prepwise-api"
    database_url: str = "postgresql+psycopg://prepwise:change-me@localhost:5432/prepwise"
    cors_allowed_origins: str = "http://localhost:3000"
    e2e_auth_enabled: bool = False
    entra_tenant_id: str = "1a782388-bf90-4ea8-af8f-bcc755f5cd7e"
    entra_tenant_subdomain: str = "prepwisecustomers"
    entra_api_client_id: str = "82773ea0-fcf3-4874-81c3-3cd0da7d00c7"
    entra_api_scope: str = "access_as_user"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "low"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    openai_max_retries: int = Field(default=1, ge=0, le=3)

    @property
    def cors_origins(self) -> list[str]:
        """Return the configured comma-separated browser origins."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def entra_issuer(self) -> str:
        """Return the exact issuer published by this External ID tenant."""
        return f"https://{self.entra_tenant_id}.ciamlogin.com/{self.entra_tenant_id}/v2.0"

    @property
    def entra_jwks_url(self) -> str:
        """Return the tenant-specific signing-key endpoint used for key rotation."""
        return (
            f"https://{self.entra_tenant_subdomain}.ciamlogin.com/"
            f"{self.entra_tenant_id}/discovery/v2.0/keys"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
