"""Tests for Discord payload construction and HTTP notification."""

from unittest.mock import patch, AsyncMock

import pytest
from fastapi import HTTPException

from proxmox_discord_notifier.discord import (
    build_discord_payload,
    send_discord_notification,
    SEVERITY_CONFIG,
)
from proxmox_discord_notifier.schemas.notify import Notify


# ── build_discord_payload ───────────────────────────────────────────


@pytest.mark.parametrize("severity", ["info", "notice", "warning", "error"])
def test_build_payload_all_severity_levels(severity):
    """Each severity produces its own color + emoji."""
    notify = Notify(
        message="test",
        title="Test",
        severity=severity,
        discord_description="desc",
    )
    payload = build_discord_payload(notify, "http://example.com/logs/abc")
    embed = payload["embeds"][0]
    cfg = SEVERITY_CONFIG[severity]
    assert embed["color"] == cfg["color"]
    assert cfg["emoji"] in embed["title"]
    # Severity field
    severities = [f["value"] for f in embed["fields"] if f["name"] == "Severity"]
    assert severity.capitalize() in severities


def test_build_payload_unknown_severity_defaults():
    """An unrecognised severity string falls back to 'unknown'."""
    notify = Notify(message="test", severity="critical")
    payload = build_discord_payload(notify, "http://example.com/logs/abc")
    embed = payload["embeds"][0]
    assert embed["color"] == SEVERITY_CONFIG["unknown"]["color"]


def test_build_payload_with_mention():
    """When mention_user_id is set, content includes the @mention."""
    notify = Notify(message="test", title="Alert", mention_user_id="123456789")
    payload = build_discord_payload(notify, "http://example.com/logs/abc")
    assert payload["content"] == "<@123456789>\n"


def test_build_payload_without_mention():
    """When mention_user_id is None, content is empty string."""
    notify = Notify(message="test", title="Alert")
    payload = build_discord_payload(notify, "http://example.com/logs/abc")
    assert payload["content"] == ""


def test_build_payload_null_title_defaults():
    """None title → 'Notification'."""
    notify = Notify(message="test", title=None)
    payload = build_discord_payload(notify, "http://example.com/logs/abc")
    assert "Notification" in payload["embeds"][0]["title"]


def test_build_payload_includes_log_url():
    """Embed includes the log URL as a hyperlink field."""
    notify = Notify(message="test")
    log_url = "https://logs.example.com/api/logs/abc123"
    payload = build_discord_payload(notify, log_url)
    embed = payload["embeds"][0]
    log_fields = [f for f in embed["fields"] if f["name"] == "Logs"]
    assert len(log_fields) == 1
    assert log_url in log_fields[0]["value"]


def test_build_payload_null_description_empty_string():
    """None discord_description → empty string in embed."""
    notify = Notify(message="test", discord_description=None)
    payload = build_discord_payload(notify, "http://example.com/logs/abc")
    assert payload["embeds"][0]["description"] == ""


def test_build_payload_has_timestamp():
    """Embed should include an ISO-format timestamp."""
    notify = Notify(message="test")
    payload = build_discord_payload(notify, "http://example.com/logs/abc")
    assert "timestamp" in payload["embeds"][0]
    # should be ISO-like
    assert "T" in payload["embeds"][0]["timestamp"]


# ── send_discord_notification ───────────────────────────────────────


@pytest.mark.asyncio
async def test_send_discord_success():
    """Successful Discord call returns the status code."""
    mock_response = AsyncMock()
    mock_response.status_code = 204

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch(
        "proxmox_discord_notifier.discord.get_http_client",
        return_value=mock_client,
    ):
        result = await send_discord_notification(
            webhook_url="https://discord.com/api/webhooks/123/abc",
            payload={"embeds": []},
        )
        assert result == 204


@pytest.mark.asyncio
async def test_send_discord_http_error():
    """4xx/5xx from Discord raises HTTPException."""
    mock_response = AsyncMock()
    mock_response.status_code = 429

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch(
        "proxmox_discord_notifier.discord.get_http_client",
        return_value=mock_client,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await send_discord_notification(
                webhook_url="https://discord.com/api/webhooks/123/abc",
                payload={"embeds": []},
            )
        assert exc_info.value.status_code == 429
        assert "failed" in exc_info.value.detail.lower()
