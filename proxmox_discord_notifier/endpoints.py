import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates

from . import config
from .discord import build_discord_payload, send_discord_notification
from .routes import LimitedBodyRoute
from .schemas.notify import Notify
from .schemas.responses import NotifyResponse
from .security import require_notify_auth, signed_log_url, verify_log_signature

# Setup Jinja2 templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter(prefix="/api", route_class=LimitedBodyRoute)
health_router = APIRouter()


@health_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def log_base_url(request: Request, log_id: str) -> str:
    if config.settings.base_url:
        return f"{str(config.settings.base_url).rstrip('/')}/api/logs/{log_id}"
    return str(request.url_for("get_log", log_id=log_id))


def resolve_log_path(log_id: str) -> Path:
    if not log_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid log ID format")
    try:
        log_directory = config.settings.log_directory.resolve()
        log_path = (log_directory / f"{log_id}.log").resolve()
        if not log_path.is_relative_to(log_directory):
            raise HTTPException(status_code=400, detail="Invalid log ID")
        return log_path
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Invalid log ID") from exc


@router.post(
    "/notify",
    status_code=200,
    response_model=NotifyResponse,
    responses={200: {"description": "Success"}, 413: {"description": "Request body too large"}},
)
async def notify(payload: Notify, request: Request) -> dict[str, Any]:
    current_settings = config.settings
    require_notify_auth(request, current_settings.notifier_api_token)
    if payload.discord_webhook and not current_settings.allow_request_webhook:
        raise HTTPException(status_code=400, detail="Request Discord webhooks are disabled")
    if payload.discord_webhook and current_settings.notifier_api_token is None:
        raise HTTPException(status_code=403, detail="Request webhooks require NOTIFIER_API_TOKEN")

    webhook_url = payload.discord_webhook or current_settings.discord_webhook
    if not webhook_url:
        raise HTTPException(status_code=400, detail="DISCORD_WEBHOOK must be configured")
    if not payload.message:
        raise HTTPException(status_code=400, detail="Message field is required and cannot be empty")
    if not current_settings.log_signing_secret:
        raise HTTPException(status_code=500, detail="LOG_SIGNING_SECRET must be configured")

    log_id = uuid.uuid4().hex
    log_url = signed_log_url(
        log_base_url(request, log_id),
        log_id,
        current_settings.log_signing_secret,
        current_settings.log_url_ttl_hours,
    )
    log_path = resolve_log_path(log_id)
    try:
        await asyncio.to_thread(log_path.write_text, payload.message, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not write log file") from exc

    status_code = await send_discord_notification(
        webhook_url=webhook_url,
        payload=build_discord_payload(payload, log_url),
    )
    return {"logs": log_url, "discord_status": status_code}


@router.get("/logs/{log_id}", name="get_log")
async def get_log(
    log_id: str, request: Request, expires: int | None = None, sig: str | None = None
):
    current_settings = config.settings
    log_path = resolve_log_path(log_id)
    if not current_settings.log_signing_secret:
        raise HTTPException(status_code=503, detail="Log links are not configured")
    verify_log_signature(log_id, expires, sig, current_settings.log_signing_secret)
    if not await asyncio.to_thread(log_path.exists):
        raise HTTPException(status_code=404, detail="Log not found")
    try:
        log_content = await asyncio.to_thread(log_path.read_text, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not read log file") from exc

    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(
            request,
            "log_viewer.html",
            {"log_id": log_id, "log_content": log_content},
        )
    return PlainTextResponse(content=log_content)
