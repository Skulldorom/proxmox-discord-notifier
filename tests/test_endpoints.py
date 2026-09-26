"""Tests for FastAPI endpoints — /notify and /logs/{log_id}."""

import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from proxmox_discord_notifier.security import make_log_signature

# ── /api/notify ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_success(client, tmp_log_dir, full_payload, mock_httpx_post, test_settings):
    """POST /api/notify should return 200 with logs URL and discord_status."""
    response = await client.post("/api/notify", json=full_payload)
    assert response.status_code == 200

    data = response.json()
    assert "logs" in data
    assert "discord_status" in data
    assert data["discord_status"] == 204
    assert "/api/logs/" in data["logs"]

    # Verify log file was written
    log_id = data["logs"].rsplit("/api/logs/", 1)[1].split("?", 1)[0]
    log_path = tmp_log_dir / f"{log_id}.log"
    assert log_path.exists()
    assert log_path.read_text() == full_payload["message"]


@pytest.mark.asyncio
async def test_notify_no_message(client, mock_httpx_post, tmp_log_dir, test_settings):
    """POST /api/notify with webhook but no message field → 400 with clear error."""
    response = await client.post("/api/notify", json={})
    assert response.status_code == 400
    assert "message" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_notify_discord_failure(client, full_payload, tmp_log_dir):
    """When Discord returns 4xx/5xx, endpoint should propagate the error."""
    from unittest.mock import AsyncMock, patch

    mock_response = AsyncMock()
    mock_response.status_code = 429

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("proxmox_discord_notifier.discord.get_http_client", return_value=mock_client):
        response = await client.post("/api/notify", json=full_payload)
        assert response.status_code == 502
        assert "retry" in response.json()["detail"].lower()


# ── /api/logs/{log_id} ──────────────────────────────────────────────


def signed_path(log_id, settings):
    expires = int(time.time()) + 60
    sig = make_log_signature(settings.log_signing_secret, log_id, expires)
    return f"/api/logs/{log_id}?expires={expires}&sig={sig}"


@pytest.mark.asyncio
async def test_logs_valid_id_plaintext(client, tmp_log_dir, test_settings):
    """GET /api/logs/{valid_id} without Accept: text/html → plain text response."""
    log_id = uuid.uuid4().hex
    content = "This is a test log\nwith multiple lines\n"
    (tmp_log_dir / f"{log_id}.log").write_text(content)

    response = await client.get(signed_path(log_id, test_settings))
    assert response.status_code == 200
    assert response.text == content


@pytest.mark.asyncio
async def test_logs_valid_id_html(client, tmp_log_dir, test_settings):
    """GET /api/logs/{valid_id} with Accept: text/html → HTML response."""
    log_id = uuid.uuid4().hex
    content = "HTML test log content"
    (tmp_log_dir / f"{log_id}.log").write_text(content)

    response = await client.get(
        signed_path(log_id, test_settings),
        headers={"Accept": "text/html"},
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Content should be HTML-escaped
    assert "HTML test log content" in response.text


@pytest.mark.asyncio
async def test_logs_html_escapes_special_chars(client, tmp_log_dir, test_settings):
    """Log content with < and > should be HTML-escaped in HTML response.
    Jinja2's |e filter handles all HTML entities correctly."""
    log_id = uuid.uuid4().hex
    content = "<script>alert('xss')</script>"
    (tmp_log_dir / f"{log_id}.log").write_text(content)

    response = await client.get(
        signed_path(log_id, test_settings),
        headers={"Accept": "text/html"},
    )
    assert response.status_code == 200
    assert "<script>" not in response.text
    # Jinja2 |e filter single-escapes (no manual pre-escaping needed)
    assert "&lt;script&gt;" in response.text


@pytest.mark.asyncio
async def test_logs_not_found(client, test_settings):
    """GET /api/logs/{nonexistent} → 404."""
    response = await client.get(signed_path(uuid.uuid4().hex, test_settings))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_logs_path_traversal_rejected(client, tmp_log_dir, test_settings):
    """GET /api/logs with path traversal characters → 400.
    httpx/Starlette decodes URL-encoded path segments, so single-encoded
    '../' gets normalised away before the route matches. Double-encoding
    (%252e%252e%252f) survives decoding: Starlette decodes once to leave
    '%2e%2e%2f' as the log_id, which fails the alnum check (contains '%')."""
    response = await client.get(signed_path("%252e%252e%252fetc%252fpasswd", test_settings))
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_logs_invalid_id_special_chars(client, test_settings):
    """GET /api/logs with non-alphanumeric chars (except - and _) → 400."""
    response = await client.get(signed_path("evil;rm%20-rf", test_settings))
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_logs_id_with_dash_underscore_accepted(client, tmp_log_dir, test_settings):
    """log_id with hyphens and underscores should be allowed."""
    log_id = "abc-def_123"
    (tmp_log_dir / f"{log_id}.log").write_text("valid")
    response = await client.get(signed_path(log_id, test_settings))
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_notify_with_base_url(client, tmp_log_dir, full_payload, mock_httpx_post):
    """When base_url is set, log URL uses it instead of request URL."""
    from unittest.mock import patch

    from proxmox_discord_notifier.config import Settings as AppSettings

    custom_settings = AppSettings(
        log_directory=tmp_log_dir,
        base_url="https://my-proxy.example.com",
        discord_webhook="https://discord.com/api/webhooks/123/default",
        log_signing_secret="01234567890123456789012345678901",
    )
    with patch("proxmox_discord_notifier.config.settings", custom_settings):
        transport = ASGITransport(app=client._transport.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/notify", json=full_payload)
            assert response.status_code == 200
            data = response.json()
            assert data["logs"].startswith("https://my-proxy.example.com/api/logs/")
