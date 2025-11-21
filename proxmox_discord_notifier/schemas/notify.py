from pydantic import BaseModel, AnyUrl, Field, field_validator
from urllib.parse import urlparse

class Notify(BaseModel):
    discord_webhook: AnyUrl | None = None
    # Limit message size to 10MB to prevent disk space exhaustion (CWE-400)
    message: str | None = Field(None, max_length=10_485_760)
    title: str | None = Field(None, max_length=256)
    severity: str | None = Field('info', max_length=50)
    discord_description: str | None = Field(None, max_length=4096)
    mention_user_id: str | None = Field(None, max_length=32)
    
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