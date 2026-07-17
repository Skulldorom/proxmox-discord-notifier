"""Tests for Settings — URL validation, base_url quoting, log_dir auto-create."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from proxmox_discord_notifier.config import Settings


# ── discord_webhook validation ──────────────────────────────────────


def test_valid_discord_webhook_accepted():
    """A valid Discord webhook URL is accepted."""
    s = Settings(discord_webhook="https://discord.com/api/webhooks/123/token")
    assert "discord.com" in str(s.discord_webhook)


def test_https_required_for_webhook():
    """Non-HTTPS webhook URL is rejected."""
    with pytest.raises(ValueError, match="must use HTTPS"):
        Settings(discord_webhook="http://discord.com/api/webhooks/123/token")


def test_discord_domain_required():
    """Non-Discord domain is rejected."""
    with pytest.raises(ValueError, match="valid Discord"):
        Settings(discord_webhook="https://example.com/api/webhooks/123/token")


def test_webhook_path_format_required():
    """URL must have /api/webhooks/ path prefix."""
    with pytest.raises(ValueError, match="Invalid Discord webhook URL format"):
        Settings(discord_webhook="https://discord.com/other/endpoint")


def test_none_webhook_accepted():
    """None webhook passes validation (it's optional)."""
    s = Settings(discord_webhook=None)
    assert s.discord_webhook is None


# ── base_url quoting ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "input_url, expected",
    [
        ('"https://proxy.example.com"', "https://proxy.example.com"),
        ("'https://proxy.example.com'", "https://proxy.example.com"),
        ("https://proxy.example.com", "https://proxy.example.com"),
        ('"http://localhost:8080"', "http://localhost:8080"),
        (None, None),
    ],
)
def test_base_url_strips_quotes(input_url, expected):
    """base_url has surrounding quotes stripped if present."""
    s = Settings(base_url=input_url)
    assert s.base_url == expected


# ── log_directory auto-create ───────────────────────────────────────


def test_log_directory_auto_created(tmp_path):
    """log_directory is created if it doesn't exist."""
    new_dir = tmp_path / "auto_logs"
    assert not new_dir.exists()
    s = Settings(log_directory=new_dir)
    assert s.log_directory.exists()
    assert s.log_directory.is_dir()


def test_log_directory_existing_no_error(tmp_path):
    """If log_directory already exists, no error."""
    existing = tmp_path / "existing_logs"
    existing.mkdir()
    s = Settings(log_directory=existing)
    assert s.log_directory == existing


# ── defaults ────────────────────────────────────────────────────────


def test_default_log_retention():
    """Default log_retention_days is 30."""
    with patch.dict(os.environ, {}, clear=True):
        s = Settings()
        assert s.log_retention_days == 30


def test_default_base_url_none():
    """Default base_url is None."""
    with patch.dict(os.environ, {}, clear=True):
        s = Settings()
        assert s.base_url is None
