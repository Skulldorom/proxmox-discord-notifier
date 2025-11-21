import uuid
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates
from typing import Any

from .discord import build_discord_payload, send_discord_notification
from .config import settings
from .schemas.notify import Notify
from .schemas.responses import NotifyResponse


# Setup Jinja2 templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


router = APIRouter(prefix="/api")


@router.post(
    "/notify",
    status_code=200,
    response_model=NotifyResponse,
    responses={200: {"description": "Success"}},
)
async def notify(
    payload: Notify,
    request: Request,
) -> dict[str, Any]:
    """
    Forward a Proxmox alert to Discord and archive the full Proxmox message.
    """

    # Use webhook from payload, or fallback to environment variable
    webhook_url = payload.discord_webhook or settings.discord_webhook
    if not webhook_url:
        raise HTTPException(
            status_code=400,
            detail="Discord webhook URL must be provided either in request payload or DISCORD_WEBHOOK environment variable",
        )

    log_id = uuid.uuid4().hex

    # Use custom base URL if configured, otherwise use request URL
    if settings.base_url:
        # Remove trailing slash from base_url if present
        base = settings.base_url.rstrip("/")
        log_url = f"{base}/api/logs/{log_id}"
    else:
        log_url = str(request.url_for("get_log", log_id=log_id))

    log_path = settings.log_directory / f"{log_id}.log"

    try:
        log_path.write_text(payload.message, encoding="utf-8")
    except Exception:
        raise HTTPException(status_code=500, detail="Could not write log file")

    discord_payload = build_discord_payload(payload, log_url)
    status_code = await send_discord_notification(
        webhook_url=webhook_url,
        payload=discord_payload,
    )

    return {"logs": log_url, "discord_status": status_code}


@router.get(
    "/logs/{log_id}",
    name="get_log",
)
async def get_log(log_id: str, request: Request):
    """
    Fetch the full text of a stored Proxmox alert message.
    Returns HTML with dark mode UI for browsers, plain text otherwise.
    """
    # Validate log_id to prevent path traversal attacks (CWE-22)
    if not log_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid log ID format")

    log_path = settings.log_directory / f"{log_id}.log"

    # Ensure the resolved path is within the log directory
    try:
        log_path = log_path.resolve()
        log_dir_resolved = settings.log_directory.resolve()
        if not str(log_path).startswith(str(log_dir_resolved)):
            raise HTTPException(status_code=400, detail="Invalid log ID")
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid log ID")

    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log not found")

    log_content = log_path.read_text(encoding="utf-8")

    # Check if request is from a browser (has Accept header with text/html)
    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header:
        # Return HTML with dark mode UI using template
        return templates.TemplateResponse(
            "log_viewer.html",
            {
                "request": request,
                "log_id": log_id,
                "log_content": log_content.replace("<", "&lt;").replace(">", "&gt;"),
            },
        )
    else:
        # Return plain text for programmatic access
        return PlainTextResponse(content=log_content)
