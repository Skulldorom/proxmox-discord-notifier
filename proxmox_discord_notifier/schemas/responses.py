from pydantic import AnyUrl, BaseModel


class NotifyResponse(BaseModel):
    """
    Response model for the /notify endpoint.
    """
    logs: AnyUrl
    discord_status: int
