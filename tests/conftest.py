"""Shared fixtures for proxmox-discord-notifier tests."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from proxmox_discord_notifier.config import Settings
from proxmox_discord_notifier.main import create_app


@pytest.fixture
def tmp_log_dir(tmp_path):
    """A temporary log directory that overrides the default."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def test_settings(tmp_log_dir):
    """Settings with a temporary log directory and no default webhook."""
    return Settings(
        log_directory=tmp_log_dir,
        discord_webhook=None,
        base_url=None,
        log_retention_days=30,
    )


@pytest.fixture
def app_with_settings(test_settings):
    """Create a FastAPI app with controlled settings."""
    with patch(
        "proxmox_discord_notifier.endpoints.settings", test_settings
    ), patch(
        "proxmox_discord_notifier.log_cleanup.settings", test_settings
    ), patch(
        "proxmox_discord_notifier.config.settings", test_settings
    ):
        app = create_app()
        yield app


@pytest.fixture
async def client(app_with_settings):
    """Async HTTP client backed by the test app."""
    transport = ASGITransport(app=app_with_settings)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_httpx_post():
    """Mock httpx.AsyncClient.post to avoid real Discord webhook calls."""
    mock_response = AsyncMock()
    mock_response.status_code = 204

    with patch(
        "proxmox_discord_notifier.discord.get_http_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        yield mock_client


@pytest.fixture
def valid_payload():
    """A minimal valid notify payload."""
    return {
        "message": "Test message",
    }


@pytest.fixture
def full_payload():
    """A full notify payload with all optional fields."""
    return {
        "discord_webhook": "https://discord.com/api/webhooks/123456789/abcdef",
        "message": "Full test message",
        "title": "Test Alert",
        "severity": "warning",
        "discord_description": "This is a test description",
        "mention_user_id": "123456789012345678",
    }
