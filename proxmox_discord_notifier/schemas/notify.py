from pydantic import AnyUrl, BaseModel, Field, field_validator

from ..validation import validate_discord_webhook


class Notify(BaseModel):
    discord_webhook: AnyUrl | None = None
    message: str | None = Field(None, max_length=10_485_760)
    title: str | None = Field(None, max_length=256)
    severity: str | None = Field("info", max_length=50)
    discord_description: str | None = Field(None, max_length=4096)
    mention_user_id: str | None = Field(None, pattern=r"^[0-9]{17,20}$")

    @field_validator("discord_webhook")
    @classmethod
    def validate_discord_webhook(cls, value):
        if value is not None:
            validate_discord_webhook(str(value))
        return value
