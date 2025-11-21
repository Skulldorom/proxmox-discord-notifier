from contextlib import asynccontextmanager
import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .endpoints import router
from . import discord
from .log_cleanup import periodic_cleanup_task, cleanup_old_logs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup: run initial cleanup and start periodic task
    cleanup_task = None
    try:
        # Run initial cleanup in background to avoid blocking startup
        asyncio.create_task(cleanup_old_logs())
        logger.info("Scheduled initial log cleanup")
        
        # Start periodic cleanup task
        cleanup_task = asyncio.create_task(periodic_cleanup_task())
        logger.info("Started periodic log cleanup task")
        
        yield
    finally:
        # Shutdown: close HTTP client if it was created
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
        
        if discord._http_client is not None:
            await discord._http_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title='Proxmox2Discord',
        description='Proxmox Discord notifier service',
        lifespan=lifespan,
        docs_url=None,  # Disable default docs to use custom one
        redoc_url="/redoc",
    )
    
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        # Load HTML template from file
        template_path = Path(__file__).parent / "templates" / "swagger_ui.html"
        try:
            template_content = template_path.read_text()
        except FileNotFoundError:
            logger.error(f"Swagger UI template not found at {template_path}")
            raise HTTPException(status_code=500, detail="Documentation template not found")
        
        # Format template with dynamic values
        html_content = template_content.format(
            title=app.title,
            openapi_url=app.openapi_url
        )
        
        return HTMLResponse(content=html_content, media_type="text/html")

    app.include_router(router)

    return app


app = create_app()

