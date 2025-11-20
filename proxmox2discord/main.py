from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .endpoints import router
from . import discord


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup: nothing needed, client created lazily
    yield
    # Shutdown: close HTTP client if it was created
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

