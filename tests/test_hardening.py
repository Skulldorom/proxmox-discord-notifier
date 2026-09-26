import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from typer.testing import CliRunner

from proxmox_discord_notifier.cli import app
from proxmox_discord_notifier.config import Settings
from proxmox_discord_notifier.discord import build_discord_payload, send_discord_notification
from proxmox_discord_notifier.schemas.notify import Notify
from proxmox_discord_notifier.security import make_log_signature


@pytest.mark.asyncio
async def test_notify_requires_configured_token(client, test_settings, valid_payload):
    test_settings.notifier_api_token = "secret-token"
    response = await client.post("/api/notify", json=valid_payload)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_notify_rejects_incorrect_token_without_processing(
    client, test_settings, valid_payload
):
    test_settings.notifier_api_token = "secret-token"
    response = await client.post(
        "/api/notify", json=valid_payload, headers={"Authorization": "Bearer incorrect-token"}
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_health_bypasses_auth(client, test_settings):
    test_settings.notifier_api_token = "secret-token"
    assert (await client.get("/health")).status_code == 200


@pytest.mark.asyncio
async def test_request_webhook_disabled_without_orphan(client, tmp_log_dir):
    response = await client.post(
        "/api/notify",
        json={"message": "test", "discord_webhook": "https://discord.com/api/webhooks/123/abc"},
    )
    assert response.status_code == 400
    assert not list(tmp_log_dir.glob("*.log"))


@pytest.mark.asyncio
async def test_authenticated_request_webhook_override(
    client, test_settings, full_payload, mock_httpx_post
):
    test_settings.notifier_api_token = "secret-token"
    test_settings.allow_request_webhook = True
    response = await client.post(
        "/api/notify", json=full_payload, headers={"Authorization": "Bearer secret-token"}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_raw_body_limit_rejects_multibyte_before_processing(
    client, test_settings, mock_httpx_post
):
    test_settings.max_request_bytes = 20
    response = await client.post(
        "/api/notify",
        content='{"message":"éééééééééé"}'.encode(),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    mock_httpx_post.post.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("message, spare_bytes", [("a" * 5, 1), ("a" * 6, 0)])
async def test_raw_body_limit_accepts_requests_at_or_below_limit(
    client, test_settings, mock_httpx_post, message, spare_bytes
):
    body = f'{{"message":"{message}"}}'.encode()
    test_settings.max_request_bytes = len(body) + spare_bytes
    response = await client.post(
        "/api/notify", content=body, headers={"content-type": "application/json"}
    )
    assert response.status_code == 200
    mock_httpx_post.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_raw_body_limit_ignores_misleading_content_length(
    client, test_settings, mock_httpx_post
):
    body = b'{"message":"too long"}'
    test_settings.max_request_bytes = len(body) - 1
    response = await client.post(
        "/api/notify",
        content=body,
        headers={"content-type": "application/json", "content-length": "1"},
    )
    assert response.status_code == 413
    mock_httpx_post.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_raw_body_limit_handles_missing_content_length(
    client, test_settings, mock_httpx_post
):
    body = b'{"message":"small"}'
    test_settings.max_request_bytes = len(body)
    response = await client.post(
        "/api/notify", content=body, headers={"content-type": "application/json"}
    )
    assert response.status_code == 200
    mock_httpx_post.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_signed_log_access(client, tmp_log_dir, test_settings):
    log_id = "abc123"
    (tmp_log_dir / f"{log_id}.log").write_text("protected")
    expires = int(time.time()) + 60
    sig = make_log_signature(test_settings.log_signing_secret, log_id, expires)
    response = await client.get(f"/api/logs/{log_id}?expires={expires}&sig={sig}")
    assert response.status_code == 200
    assert response.text == "protected"
    assert (await client.get(f"/api/logs/{log_id}")).status_code == 403
    assert (await client.get(f"/api/logs/changed?expires={expires}&sig={sig}")).status_code == 403


@pytest.mark.parametrize("mention", ["abc", "1234567890123456", "123456789012345678901"])
def test_mention_requires_discord_snowflake(mention):
    with pytest.raises(ValidationError):
        Notify(message="test", mention_user_id=mention)


@pytest.mark.asyncio
async def test_signed_log_access_rejects_expired_and_tampered_values(
    client, tmp_log_dir, test_settings
):
    log_id = "abc123"
    (tmp_log_dir / f"{log_id}.log").write_text("protected")
    expires = int(time.time()) + 60
    signature = make_log_signature(test_settings.log_signing_secret, log_id, expires)
    expired = int(time.time()) - 1
    expired_signature = make_log_signature(test_settings.log_signing_secret, log_id, expired)
    wrong_key_signature = make_log_signature("x" * 32, log_id, expires)

    assert (
        await client.get(f"/api/logs/{log_id}?expires={expired}&sig={expired_signature}")
    ).status_code == 403
    assert (
        await client.get(f"/api/logs/{log_id}?expires={expires + 1}&sig={signature}")
    ).status_code == 403
    assert (
        await client.get(f"/api/logs/{log_id}?expires={expires}&sig={wrong_key_signature}")
    ).status_code == 403
    assert (
        await client.get(f"/api/logs/{log_id}?expires={expires}&sig=not-a-signature")
    ).status_code == 403


def test_allowed_mentions_are_restricted():
    plain = build_discord_payload(Notify(message="test"), "https://logs.example/test")
    mentioned = build_discord_payload(
        Notify(message="test", mention_user_id="123456789012345678"), "https://logs.example/test"
    )
    assert plain["allowed_mentions"] == {"parse": []}
    assert mentioned["allowed_mentions"] == {"parse": [], "users": ["123456789012345678"]}


@pytest.mark.asyncio
async def test_discord_timeout_maps_to_gateway_timeout():
    client = AsyncMock()
    client.post.side_effect = httpx.TimeoutException("timeout")
    with patch("proxmox_discord_notifier.discord.get_http_client", return_value=client):
        with pytest.raises(HTTPException) as error:
            await send_discord_notification("https://discord.com/api/webhooks/1/a", {})
    assert error.value.status_code == 504


@pytest.mark.asyncio
async def test_discord_rate_limit_retries_without_real_sleep():
    request = httpx.Request("POST", "https://discord.com/api/webhooks/1/a")
    rate_limited = httpx.Response(429, headers={"Retry-After": "0"}, request=request)
    success = httpx.Response(204, request=request)
    client = AsyncMock()
    client.post.side_effect = [rate_limited, success]
    with patch("proxmox_discord_notifier.discord.get_http_client", return_value=client):
        assert await send_discord_notification("https://discord.com/api/webhooks/1/a", {}) == 204
    assert client.post.await_count == 2


@pytest.mark.asyncio
async def test_discord_request_error_maps_to_bad_gateway():
    client = AsyncMock()
    client.post.side_effect = httpx.RequestError("network failure")
    with patch("proxmox_discord_notifier.discord.get_http_client", return_value=client):
        with pytest.raises(HTTPException) as error:
            await send_discord_notification("https://discord.com/api/webhooks/1/a", {})
    assert error.value.status_code == 502


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 404])
async def test_discord_permanent_errors_are_not_retried(status):
    request = httpx.Request("POST", "https://discord.com/api/webhooks/1/a")
    client = AsyncMock()
    client.post.return_value = httpx.Response(status, request=request)
    with patch("proxmox_discord_notifier.discord.get_http_client", return_value=client):
        with pytest.raises(HTTPException) as error:
            await send_discord_notification("https://discord.com/api/webhooks/1/a", {})
    assert error.value.status_code == status
    client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_discord_transient_error_retries_then_succeeds():
    request = httpx.Request("POST", "https://discord.com/api/webhooks/1/a")
    client = AsyncMock()
    client.post.side_effect = [
        httpx.Response(503, request=request),
        httpx.Response(204, request=request),
    ]
    with (
        patch("proxmox_discord_notifier.discord.get_http_client", return_value=client),
        patch("proxmox_discord_notifier.discord.asyncio.sleep", new_callable=AsyncMock),
    ):
        assert await send_discord_notification("https://discord.com/api/webhooks/1/a", {}) == 204
    assert client.post.await_count == 2


@pytest.mark.asyncio
async def test_discord_retry_exhaustion_maps_to_bad_gateway():
    request = httpx.Request("POST", "https://discord.com/api/webhooks/1/a")
    client = AsyncMock()
    client.post.return_value = httpx.Response(503, request=request)
    with (
        patch("proxmox_discord_notifier.discord.get_http_client", return_value=client),
        patch("proxmox_discord_notifier.discord.asyncio.sleep", new_callable=AsyncMock),
    ):
        with pytest.raises(HTTPException) as error:
            await send_discord_notification("https://discord.com/api/webhooks/1/a", {})
    assert error.value.status_code == 502
    assert client.post.await_count == 3


@pytest.mark.parametrize("retention", [-1, -5])
def test_negative_retention_rejected(retention):
    with pytest.raises(ValidationError):
        Settings(log_retention_days=retention)


@pytest.mark.parametrize("base_url", ["ftp://example.com", "not a url"])
def test_invalid_base_url_rejected(base_url):
    with pytest.raises(ValidationError):
        Settings(base_url=base_url)


def test_cli_config_precedence(tmp_path):
    config = tmp_path / "config.py"
    config.write_text("CONFIG = {'host': '0.0.0.0', 'port': 9000, 'log_level': 'warning'}")
    with patch("proxmox_discord_notifier.cli.uvicorn.run") as run:
        result = CliRunner().invoke(app, ["--config", str(config), "--port", "7000"])
    assert result.exit_code == 0
    assert run.call_args.kwargs["host"] == "0.0.0.0"
    assert run.call_args.kwargs["port"] == 7000
    assert run.call_args.kwargs["log_level"] == "warning"


def test_cli_rejects_non_mapping_config(tmp_path):
    config = tmp_path / "config.py"
    config.write_text("CONFIG = []")
    result = CliRunner().invoke(app, ["--config", str(config)])
    assert result.exit_code != 0
    assert "CONFIG must be a mapping" in result.output
