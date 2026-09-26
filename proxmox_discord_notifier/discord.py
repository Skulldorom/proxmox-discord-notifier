import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import AnyUrl

SEVERITY_CONFIG = {
    "info": {"color": 0x3498DB, "emoji": "ℹ️"},
    "notice": {"color": 0x2ECC71, "emoji": "🔔"},
    "warning": {"color": 0xF1C40F, "emoji": "⚠️"},
    "error": {"color": 0xE74C3C, "emoji": "❌"},
    "unknown": {"color": 0x95A5A6, "emoji": "❔"},
}
MAX_ATTEMPTS = 3
MAX_RETRY_DELAY_SECONDS = 5.0
logger = logging.getLogger(__name__)
_http_client: httpx.AsyncClient | None = None


async def close_client() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=10.0, limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
    return _http_client


def build_discord_payload(payload, log_url: str) -> dict:
    severity = (payload.severity or "unknown").lower()
    cfg = SEVERITY_CONFIG.get(severity, SEVERITY_CONFIG["unknown"])
    mention = payload.mention_user_id
    allowed_mentions = {"parse": [], "users": [mention]} if mention else {"parse": []}
    embed = {
        "title": f"{cfg['emoji']} {payload.title or 'Notification'}",
        "description": payload.discord_description or "",
        "color": cfg["color"],
        "fields": [
            {"name": "Severity", "value": severity.capitalize(), "inline": True},
            {"name": "Logs", "value": f"[View full logs]({log_url})", "inline": True},
        ],
        "timestamp": datetime.now().isoformat(),
    }
    return {
        "content": f"<@{mention}>\n" if mention else "",
        "allowed_mentions": allowed_mentions,
        "embeds": [embed],
    }


def retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if isinstance(response, httpx.Response):
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), MAX_RETRY_DELAY_SECONDS)
            except ValueError:
                pass
        try:
            retry_after_json = response.json().get("retry_after")
            if retry_after_json is not None:
                return min(float(retry_after_json), MAX_RETRY_DELAY_SECONDS)
        except (TypeError, ValueError, AttributeError):
            pass
    return min(0.25 * (2**attempt), MAX_RETRY_DELAY_SECONDS)


async def send_discord_notification(
    webhook_url: AnyUrl,
    payload: dict[str, Any],
    timeout: float = 10.0,
) -> int:
    """Send a Discord webhook with bounded retries for transient failures."""
    client = get_http_client()
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = await client.post(str(webhook_url), json=payload, timeout=timeout)
        except httpx.TimeoutException as exc:
            logger.warning("Discord webhook request timed out")
            raise HTTPException(status_code=504, detail="Discord webhook timed out") from exc
        except httpx.RequestError as exc:
            logger.warning("Discord webhook network request failed")
            raise HTTPException(status_code=502, detail="Discord webhook network failure") from exc

        if response.status_code < 400:
            return response.status_code
        if response.status_code not in {429, 500, 502, 503, 504}:
            raise HTTPException(
                status_code=response.status_code, detail="Discord webhook call failed"
            )
        if attempt == MAX_ATTEMPTS - 1:
            raise HTTPException(status_code=502, detail="Discord webhook retry limit reached")
        await asyncio.sleep(retry_delay(response, attempt))

    raise AssertionError("unreachable")
