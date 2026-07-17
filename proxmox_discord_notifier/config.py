from pathlib import Path

from pydantic import AnyUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .validation import validate_discord_webhook


class Settings(BaseSettings):
    log_directory: Path = Path().cwd() / "logs"
    discord_webhook: AnyUrl | None = None
    base_url: str | None = None  # Custom base URL for when behind a proxy
    log_retention_days: int = 30  # Number of days to keep logs (0 = keep forever)

    @field_validator("log_directory", mode='after')
    def create_log_directory(cls, v):
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator('base_url', mode='before')
    @classmethod
    def clean_base_url(cls, v):
        """Strip quotes from base_url if present"""
        if v is None or not isinstance(v, str):
            return v
        # Remove surrounding quotes if present
        return v.strip('\'"')

    @field_validator('discord_webhook')
    @classmethod
    def validate_discord_webhook(cls, v):
        """Validate webhook URL to prevent SSRF attacks (CWE-918)"""
        if v is None:
            return v

        validate_discord_webhook(str(v))
        return v

    model_config = SettingsConfigDict()


settings = Settings()
