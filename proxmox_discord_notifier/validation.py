"""Shared validation utilities for the Proxmox Discord Notifier."""

from urllib.parse import urlparse


def validate_discord_webhook(url_str: str) -> str:
    """Validate a Discord webhook URL to prevent SSRF attacks (CWE-918).

    Checks HTTPS, webhook path format, and Discord domain ownership.
    Returns the URL string unchanged on success, raises ValueError on failure.
    """
    parsed = urlparse(url_str)

    # Ensure HTTPS (check first as it's fastest)
    if parsed.scheme != "https":
        raise ValueError("Webhook URL must use HTTPS")

    # Validate it's a webhook endpoint
    if not parsed.path.startswith("/api/webhooks/"):
        raise ValueError("Invalid Discord webhook URL format")

    # Only allow Discord webhook URLs
    netloc = parsed.netloc
    if not (
        netloc == "discord.com"
        or netloc == "discordapp.com"
        or netloc.endswith(".discord.com")
        or netloc.endswith(".discordapp.com")
    ):
        raise ValueError("Webhook URL must be a valid Discord webhook URL")

    return url_str
