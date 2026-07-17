import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import discord
from .endpoints import router, health_router
from .log_cleanup import cleanup_old_logs, periodic_cleanup_task

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
        # Shutdown: cancel periodic cleanup and close HTTP client
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

        await discord.close_client()


def create_app() -> FastAPI:
    app = FastAPI(
        title='Proxmox Discord Notifier',
        description='Proxmox Discord notifier service',
        lifespan=lifespan,
    )

    app.include_router(router)
    app.include_router(health_router)

    return app


app = create_app()

