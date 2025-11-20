from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, AnyUrl
from urllib.parse import urlparse


class Settings(BaseSettings):
    log_directory: Path = Path().cwd() / "logs"
    discord_webhook: AnyUrl | None = None
    # log_retention_days: int = 7

    @field_validator("log_directory", mode='after')
    def create_log_directory(cls, v):
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator('discord_webhook')
    @classmethod
    def validate_discord_webhook(cls, v):
        """Validate webhook URL to prevent SSRF attacks (CWE-918)"""
        if v is None:
            return v
            
        url = str(v)
        parsed = urlparse(url)
        
        # Ensure HTTPS (check first as it's fastest)
        if parsed.scheme != 'https':
            raise ValueError('Webhook URL must use HTTPS')
        
        # Validate it's a webhook endpoint
        if not parsed.path.startswith('/api/webhooks/'):
            raise ValueError('Invalid Discord webhook URL format')
        
        # Only allow Discord webhook URLs
        netloc = parsed.netloc
        if not (netloc == 'discord.com' or netloc == 'discordapp.com' or 
                netloc.endswith('.discord.com') or netloc.endswith('.discordapp.com')):
            raise ValueError('Webhook URL must be a valid Discord webhook URL')
            
        return v

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')


settings = Settings()