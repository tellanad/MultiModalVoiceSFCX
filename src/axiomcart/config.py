"""Application configuration loaded from environment and .env."""
from typing import Optional
from pydantic import HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"

    # Salesforce Configuration
    salesforce_instance_url: str = "https://example.my.salesforce.com"
    salesforce_client_id: str = ""
    salesforce_client_secret: SecretStr = SecretStr("")
    salesforce_api_version: str = "v68.0"

    @field_validator("salesforce_instance_url", mode="before")
    @classmethod
    def normalize_salesforce_url(cls, v: str) -> str:
        s = str(v or "https://example.my.salesforce.com").strip().rstrip("/")
        if s.startswith("ttps://"):
            return "h" + s
        elif not s.startswith("http://") and not s.startswith("https://"):
            return "https://" + s
        return s

    # Database
    database_url: Optional[str] = None

    # LiveKit
    livekit_url: Optional[str] = None
    livekit_api_key: Optional[str] = None
    livekit_api_secret: Optional[SecretStr] = None

    # Inventory
    inventory_provider: str = "mock"
    inventory_base_url: Optional[str] = None
    inventory_api_key: Optional[SecretStr] = None


settings = Settings()
