from pathlib import Path

from pydantic import AnyUrl, Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .validation import validate_discord_webhook


class Settings(BaseSettings):
    log_directory: Path = Path.cwd() / "logs"
    discord_webhook: AnyUrl | None = None
    notifier_api_token: str | None = Field(default=None, min_length=1)
    allow_request_webhook: bool = False
    max_request_bytes: int = Field(default=10_550_000, ge=1)
    base_url: HttpUrl | None = None
    log_retention_days: int = Field(default=30, ge=0)
    log_signing_secret: str | None = Field(default=None, min_length=32)
    log_url_ttl_hours: int = Field(default=24, ge=1, le=24 * 365)

    @field_validator("log_directory", mode="after")
    @classmethod
    def create_log_directory(cls, value: Path) -> Path:
        value.mkdir(parents=True, exist_ok=True)
        return value

    @field_validator("base_url", mode="before")
    @classmethod
    def clean_base_url(cls, value):
        if value is None or not isinstance(value, str):
            return value
        return value.strip("'\"").rstrip("/")

    @field_validator("discord_webhook")
    @classmethod
    def validate_discord_webhook(cls, value):
        if value is not None:
            validate_discord_webhook(str(value))
        return value

    model_config = SettingsConfigDict()


settings = Settings()
