"""Application configuration loaded from environment and .env."""
from typing import Optional
from pydantic import HttpUrl, SecretStr
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
    salesforce_instance_url: HttpUrl = "https://example.my.salesforce.com"  # type: ignore[assignment]
    salesforce_client_id: str = ""
    salesforce_client_secret: SecretStr = SecretStr("")
    salesforce_api_version: str = "v68.0"

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
