"""Tests for the Notify Pydantic schema — validation, SSRF guard, field limits."""

import pytest
from pydantic import ValidationError

from proxmox_discord_notifier.schemas.notify import Notify

# ── valid payloads ──────────────────────────────────────────────────


def test_notify_minimal_valid():
    """A payload with only the message field should validate."""
    notify = Notify(message="Hello, world!")
    assert notify.message == "Hello, world!"
    assert notify.discord_webhook is None
    assert notify.title is None
    assert notify.severity == "info"
    assert notify.discord_description is None
    assert notify.mention_user_id is None


def test_notify_full_valid():
    """A payload with every field populated should validate."""
    notify = Notify(
        discord_webhook="https://discord.com/api/webhooks/123/abc",
        message="Proxmox alert: node offline",
        title="Node Down",
        severity="error",
        discord_description="The node 'pve-01' is unreachable.",
        mention_user_id="123456789012345678",
    )
    assert notify.severity == "error"
    assert notify.title == "Node Down"
    assert str(notify.discord_webhook) == "https://discord.com/api/webhooks/123/abc"


def test_notify_none_webhook_passes():
    """discord_webhook=None is allowed (fallback to env var)."""
    notify = Notify(message="test", discord_webhook=None)
    assert notify.discord_webhook is None


def test_notify_empty_message_none_passes():
    """message=None is allowed."""
    notify = Notify(message=None)
    assert notify.message is None


# ── webhook URL validation (SSRF guard) ─────────────────────────────


@pytest.mark.parametrize(
    "url, expected_error",
    [
        ("http://discord.com/api/webhooks/xyz", "must use HTTPS"),
        ("https://evil.com/api/webhooks/xyz", "must be a valid Discord"),
        ("https://discord.com/api/other/xyz", "Invalid Discord webhook URL format"),
        ("ftp://discord.com/api/webhooks/xyz", "must use HTTPS"),
    ],
)
def test_notify_webhook_ssrf_rejected(url, expected_error):
    """SSRF guard rejects non-HTTPS, non-Discord, and malformed webhook URLs."""
    with pytest.raises(ValidationError) as exc_info:
        Notify(message="test", discord_webhook=url)
    errors = str(exc_info.value).lower()
    assert expected_error.lower() in errors


def test_notify_webhook_discordapp_domain_accepted():
    """The legacy discordapp.com domain is also valid."""
    notify = Notify(
        message="test",
        discord_webhook="https://discordapp.com/api/webhooks/123/token",
    )
    assert "discordapp.com" in str(notify.discord_webhook)


def test_notify_webhook_subdomain_accepted():
    """Subdomains like canary.discord.com should be accepted."""
    notify = Notify(
        message="test",
        discord_webhook="https://canary.discord.com/api/webhooks/123/token",
    )
    assert "canary.discord.com" in str(notify.discord_webhook)


# ── field length limits ─────────────────────────────────────────────


def test_message_exceeds_max_length():
    """Message over 10 MiB is rejected."""
    huge = "x" * (10_485_761)  # one byte over
    with pytest.raises(ValidationError):
        Notify(message=huge)


def test_message_at_max_length_passes():
    """Message at exactly 10 MiB should pass."""
    huge = "x" * 10_485_760
    notify = Notify(message=huge)
    assert len(notify.message) == 10_485_760


def test_title_max_length():
    """Title limited to 256 chars."""
    with pytest.raises(ValidationError):
        Notify(message="test", title="x" * 257)
    # at max should pass
    notify = Notify(message="test", title="x" * 256)
    assert len(notify.title) == 256


def test_severity_max_length():
    """Severity limited to 50 chars."""
    with pytest.raises(ValidationError):
        Notify(message="test", severity="x" * 51)
    notify = Notify(message="test", severity="x" * 50)
    assert len(notify.severity) == 50


def test_discord_description_max_length():
    """Description limited to 4096 chars."""
    with pytest.raises(ValidationError):
        Notify(message="test", discord_description="x" * 4097)
    notify = Notify(message="test", discord_description="x" * 4096)
    assert len(notify.discord_description) == 4096


def test_mention_user_id_max_length():
    """mention_user_id limited to 32 chars."""
    with pytest.raises(ValidationError):
        Notify(message="test", mention_user_id="x" * 33)
    notify = Notify(message="test", mention_user_id="x" * 32)
    assert len(notify.mention_user_id) == 32
