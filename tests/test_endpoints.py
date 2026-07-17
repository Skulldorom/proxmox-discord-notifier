"""Tests for FastAPI endpoints — /notify and /logs/{log_id}."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

# ── /api/notify ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_success(client, tmp_log_dir, full_payload, mock_httpx_post):
    """POST /api/notify should return 200 with logs URL and discord_status."""
    response = await client.post("/api/notify", json=full_payload)
    assert response.status_code == 200

    data = response.json()
    assert "logs" in data
    assert "discord_status" in data
    assert data["discord_status"] == 204
    assert "/api/logs/" in data["logs"]

    # Verify log file was written
    log_id = data["logs"].rsplit("/", 1)[-1]
    log_path = tmp_log_dir / f"{log_id}.log"
    assert log_path.exists()
    assert log_path.read_text() == full_payload["message"]


@pytest.mark.asyncio
async def test_notify_missing_webhook_400(client, valid_payload):
    """POST /api/notify without a webhook (no payload, no env) → 400."""
    response = await client.post("/api/notify", json=valid_payload)
    assert response.status_code == 400
    assert "webhook" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_notify_no_message(client, mock_httpx_post, tmp_log_dir):
    """POST /api/notify with webhook but no message field — message=None is
    accepted by the schema but write_text(None) fails at the I/O layer (500).
    This is expected current behaviour; the code path for None messages should
    eventually be guarded earlier."""
    response = await client.post(
        "/api/notify",
        json={
            "discord_webhook": "https://discord.com/api/webhooks/123/abc",
        },
    )
    # Currently returns 500 because write_text(None) raises TypeError.
    # If the code is fixed to handle None gracefully, adjust to 200.
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_notify_discord_failure(client, full_payload, tmp_log_dir):
    """When Discord returns 4xx/5xx, endpoint should propagate the error."""
    from unittest.mock import AsyncMock, patch

    mock_response = AsyncMock()
    mock_response.status_code = 429

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch(
        "proxmox_discord_notifier.discord.get_http_client", return_value=mock_client
    ):
        response = await client.post("/api/notify", json=full_payload)
        assert response.status_code == 429
        assert "failed" in response.json()["detail"].lower()


# ── /api/logs/{log_id} ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logs_valid_id_plaintext(client, tmp_log_dir):
    """GET /api/logs/{valid_id} without Accept: text/html → plain text response."""
    log_id = uuid.uuid4().hex
    content = "This is a test log\nwith multiple lines\n"
    (tmp_log_dir / f"{log_id}.log").write_text(content)

    response = await client.get(f"/api/logs/{log_id}")
    assert response.status_code == 200
    assert response.text == content


@pytest.mark.asyncio
async def test_logs_valid_id_html(client, tmp_log_dir):
    """GET /api/logs/{valid_id} with Accept: text/html → HTML response."""
    log_id = uuid.uuid4().hex
    content = "HTML test log content"
    (tmp_log_dir / f"{log_id}.log").write_text(content)

    response = await client.get(
        f"/api/logs/{log_id}",
        headers={"Accept": "text/html"},
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Content should be HTML-escaped
    assert "HTML test log content" in response.text


@pytest.mark.asyncio
async def test_logs_html_escapes_special_chars(client, tmp_log_dir):
    """Log content with < and > should be HTML-escaped in HTML response.
    Jinja2's |e filter handles all HTML entities correctly."""
    log_id = uuid.uuid4().hex
    content = "<script>alert('xss')</script>"
    (tmp_log_dir / f"{log_id}.log").write_text(content)

    response = await client.get(
        f"/api/logs/{log_id}",
        headers={"Accept": "text/html"},
    )
    assert response.status_code == 200
    assert "<script>" not in response.text
    # Jinja2 |e filter single-escapes (no manual pre-escaping needed)
    assert "&lt;script&gt;" in response.text


@pytest.mark.asyncio
async def test_logs_not_found(client):
    """GET /api/logs/{nonexistent} → 404."""
    response = await client.get(f"/api/logs/{uuid.uuid4().hex}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_logs_path_traversal_rejected(client, tmp_log_dir):
    """GET /api/logs with path traversal characters → 400.
    httpx/Starlette decodes URL-encoded path segments, so single-encoded
    '../' gets normalised away before the route matches. Double-encoding
    (%252e%252e%252f) survives decoding: Starlette decodes once to leave
    '%2e%2e%2f' as the log_id, which fails the alnum check (contains '%')."""
    response = await client.get("/api/logs/%252e%252e%252fetc%252fpasswd")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_logs_invalid_id_special_chars(client):
    """GET /api/logs with non-alphanumeric chars (except - and _) → 400."""
    response = await client.get("/api/logs/evil;rm%20-rf")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_logs_id_with_dash_underscore_accepted(client, tmp_log_dir):
    """log_id with hyphens and underscores should be allowed."""
    log_id = "abc-def_123"
    (tmp_log_dir / f"{log_id}.log").write_text("valid")
    response = await client.get(f"/api/logs/{log_id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_notify_with_base_url(client, tmp_log_dir, full_payload, mock_httpx_post):
    """When base_url is set, log URL uses it instead of request URL."""
    from unittest.mock import patch

    from proxmox_discord_notifier.config import Settings as AppSettings

    custom_settings = AppSettings(
        log_directory=tmp_log_dir,
        base_url="https://my-proxy.example.com",
        discord_webhook=None,
    )
    with patch("proxmox_discord_notifier.endpoints.settings", custom_settings):
        transport = ASGITransport(app=client._transport.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/notify", json=full_payload)
            assert response.status_code == 200
            data = response.json()
            assert data["logs"].startswith("https://my-proxy.example.com/api/logs/")
