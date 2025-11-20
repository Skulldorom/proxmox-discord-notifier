import uvicorn
import typer

from pathlib import Path
from typing import Optional


app = typer.Typer(help="Manage and run the proxmox2discord web server.")


@app.command()
def serve(
    host: str = typer.Option(
        "127.0.0.1", "--host", "-h", help="Host/IP to bind the server on."
    ),
    port: int = typer.Option(
        6068, "--port", "-p", help="Port to listen on."
    ),
    log_level: str = typer.Option(
        "info", "--log-level", "-l", help="Uvicorn log level."
    ),
    uvicorn_config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Path to a Uvicorn config file (Python).",
    ),
):
    """ Start proxmox2discord web server. """

    uvicorn_kwargs = {
        "app": "proxmox2discord.main:app",
        "host": host,
        "port": port,
        "log_level": log_level,
    }

    if uvicorn_config:
        # Validate config file is a Python file to prevent unexpected behavior
        if not str(uvicorn_config).endswith('.py'):
            typer.echo("Error: Config file must be a Python (.py) file", err=True)
            raise typer.Exit(code=1)
        
        # Load additional config from file
        import importlib.util
        spec = importlib.util.spec_from_file_location("uvicorn_config", uvicorn_config)
        if spec and spec.loader:
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)
            # Merge config from module with CLI args (CLI args take precedence)
            if hasattr(config_module, 'CONFIG'):
                uvicorn_kwargs.update(config_module.CONFIG)

    uvicorn.run(**uvicorn_kwargs)


if __name__ == "__main__":
    app()