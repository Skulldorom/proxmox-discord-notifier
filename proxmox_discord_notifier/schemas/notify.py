from pydantic import AnyUrl, BaseModel, Field, field_validator

from ..validation import validate_discord_webhook


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

        validate_discord_webhook(str(v))
        return v
