import importlib.util
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

app = typer.Typer(help="Manage and run the proxmox-discord-notifier web server.")


def load_config(path: Path) -> dict:
    if path.suffix != ".py":
        raise typer.BadParameter("Config file must be a Python (.py) file", param_hint="--config")
    spec = importlib.util.spec_from_file_location("uvicorn_config", path)
    if spec is None or spec.loader is None:
        raise typer.BadParameter("Could not load config file", param_hint="--config")
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    config = getattr(config_module, "CONFIG", {})
    if not isinstance(config, Mapping):
        raise typer.BadParameter("CONFIG must be a mapping", param_hint="--config")
    return dict(config)


@app.command()
def serve(
    ctx: typer.Context,
    host: Annotated[
        str, typer.Option("--host", "-h", help="Host/IP to bind the server on.")
    ] = None,
    port: Annotated[int, typer.Option("--port", "-p", help="Port to listen on.")] = None,
    log_level: Annotated[str, typer.Option("--log-level", "-l", help="Uvicorn log level.")] = None,
    uvicorn_config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, file_okay=True, dir_okay=False),
    ] = None,
):
    """Start the notifier. Config defaults < explicitly passed CLI options."""
    uvicorn_kwargs = {"app": "proxmox_discord_notifier.main:app"}
    if uvicorn_config:
        uvicorn_kwargs.update(load_config(uvicorn_config))

    defaults = {"host": "127.0.0.1", "port": 6068, "log_level": "info"}
    for name, value in {"host": host, "port": port, "log_level": log_level}.items():
        if value is not None:
            uvicorn_kwargs[name] = value
        elif name not in uvicorn_kwargs:
            uvicorn_kwargs[name] = defaults[name]
    uvicorn.run(**uvicorn_kwargs)


if __name__ == "__main__":
    app()
