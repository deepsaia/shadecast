"""The serve command: resolve the settings once and hand them to uvicorn, which runs the app.

uvicorn is imported when the command runs, so ``sdc --help`` never pays for it.
"""

from __future__ import annotations

import os
import socket
import threading
import webbrowser
from pathlib import Path
from typing import Annotated

import typer

from .console import console
from .console import error_console
from .exit_codes import FAILED
from .server.settings import ServerSettings

FACTORY = "shadecast.server.app:create_app"


def serve(
    host: Annotated[str | None, typer.Option("--host", help="Address to bind.")] = None,
    port: Annotated[int | None, typer.Option("--port", help="Port to serve on.")] = None,
    data: Annotated[Path | None, typer.Option("--data", help="The data root.")] = None,
    reload: Annotated[bool, typer.Option("--reload", help="Restart on code changes.")] = False,
    open_browser: Annotated[bool, typer.Option("--open/--no-open")] = True,
) -> None:
    """Serve the API and the dashboard for whatever data is on disk.

    Each default yields to its SDC_HOST, SDC_PORT or SDC_DATA variable, which yields to the flag.
    """
    import uvicorn

    settings = resolve(host, port, data, reload)
    if port_in_use(settings.host, settings.port):
        error_console.print(
            f"port {settings.port} is already in use on {settings.host}; stop what holds it, "
            f"or pass --port with another number.",
            style="red",
            markup=False,
        )
        raise typer.Exit(code=FAILED)
    # A reloading server imports the app by name in a child process; the variables carry the
    # resolved settings to it. Writing them here is the one place the environment is touched.
    os.environ.update(settings.environment())
    url = f"http://{settings.host}:{settings.port}/"
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    console.print(f"[green]shadecast[/] on {url}  (ctrl-c to stop)")
    uvicorn.run(FACTORY, factory=True, host=settings.host, port=settings.port, reload=settings.reload)


def resolve(host: str | None, port: int | None, data: Path | None, reload: bool) -> ServerSettings:
    """Defaults, then the environment, then whichever flags were given."""
    given: dict[str, object] = {"reload": reload}
    if host is not None:
        given["host"] = host
    if port is not None:
        given["port"] = port
    if data is not None:
        given["data_root"] = data
    return ServerSettings.from_environment().model_copy(update=given)


def port_in_use(host: str, port: int) -> bool:
    """Whether something already listens where the server would bind, checked before it starts."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex((host, port)) == 0
