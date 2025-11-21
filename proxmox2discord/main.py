from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, HTTPException

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
        logger.info("Running initial log cleanup...")
        await cleanup_old_logs()
        
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
    )

    app.include_router(router)

    return app


app = create_app()

