"""Command line for the local dashboard.

Builds a static bundle then serves it from the standard library. No web framework,
no build step, no CDN: the bundle is plain files, so it can be zipped, archived or
served anywhere, which matters for reproducing a result years later.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from .cities import CORPUS
from .console import console
from .dash.builder import build_city
from .dash.server import serve

logger = logging.getLogger(__name__)

BUNDLE_ROOTS = (Path("data/cities"), Path("out/corpus"))
DEFAULT_OUT = Path("data/dash")

app = typer.Typer(name="dash", help="Interactive local walkthrough of what we do to a city.")


def find_bundle(city: str) -> Path | None:
    """Locate a built bundle for a city, preferring the canonical location."""
    for root in BUNDLE_ROOTS:
        candidate = root / city
        if (candidate / "provenance.json").exists():
            return candidate
    return None


def discover() -> list[tuple[str, Path, Path]]:
    """Every city that has both a bundle and generated physics."""
    found = []
    for city in CORPUS:
        surrogate_dir = Path("data/surrogate") / city
        bundle = find_bundle(city)
        if bundle and (surrogate_dir / "baseline" / "tmrt_daylight.npy").exists():
            found.append((city, bundle, surrogate_dir))
    return found


@app.callback(invoke_without_command=True)
def main(
    port: Annotated[int, typer.Option("--port", help="Port to serve on.")] = 8765,
    out: Annotated[Path | None, typer.Option("--out", help="Bundle directory.")] = None,
    rebuild: Annotated[bool, typer.Option("--rebuild", help="Regenerate the bundle.")] = False,
    open_browser: Annotated[bool, typer.Option("--open/--no-open")] = True,
) -> None:
    """Build the dashboard bundle if needed, then serve it."""
    destination = out if out else DEFAULT_OUT
    index = destination / "index.json"

    if rebuild or not index.exists():
        cities = discover()
        if not cities:
            console.print(
                "[red]No city has both a bundle and generated physics.[/] "
                "Run 'shadecast build <city>' then 'shadecast surrogate generate'."
            )
            raise typer.Exit(code=1)

        destination.mkdir(parents=True, exist_ok=True)
        payload = []
        with console.status("[cyan]building dashboard bundle[/]") as status:
            for city, bundle, surrogate_dir in cities:
                status.update(f"[cyan]{city}[/]: rendering frames and plans")
                payload.append(build_city(city, bundle, surrogate_dir, destination))
                console.print(
                    f"  [green]{city}[/]: {len(payload[-1]['frames'])} hourly frames, "
                    f"{len(payload[-1]['plans'])} plans"
                )
        index.write_text(json.dumps({"cities": payload}))
        app_html = Path(__file__).parent / "dash" / "app.html"
        (destination / "index.html").write_text(app_html.read_text())

    console.print(f"[green]shadecast dash[/] on http://127.0.0.1:{port}/  (ctrl-c to stop)")
    serve(destination, port=port, open_browser=open_browser)
