"""Command line for the local dashboard.

Builds a static bundle then serves it from the standard library. No web framework,
no build step, no CDN: the bundle is plain files, so it can be zipped, archived or
served anywhere, which matters for reproducing a result years later.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Annotated

import typer

from . import cities
from .console import console
from .corpus import tile_paths
from .corpus.tile_paths import TilePaths
from .dash.builder import build_index
from .dash.server import serve

logger = logging.getLogger(__name__)

# The same directory that gets published. Serving the walkthrough locally from one
# bundle and publishing another is how the two quietly drift apart, which is exactly
# what happened once: `shadecast dash` kept showing a build from hours earlier while
# the public page had moved on.
DEFAULT_OUT = Path("docs")

app = typer.Typer(name="dash", help="Interactive local walkthrough of what we do to a city.")


def tile_entries(key: str, urban_centre: int) -> list[tuple[str, Path, Path]]:
    """Every tile of a city with a bundle and a baseline field, named by key and tile."""
    ready = [
        paths
        for paths in TilePaths.existing(tile_paths.TILES_ROOT, urban_centre)
        if paths.stages().get("bundle") and paths.stages().get("baseline")
    ]
    if len(ready) == 1:
        return [(key, ready[0].bundle, ready[0].surrogate)]
    return [(f"{key}-{paths.tile.id}", paths.bundle, paths.surrogate) for paths in ready]


def discover() -> list[tuple[str, Path, Path]]:
    """Every tile with both a bundle and generated physics, in selection order."""
    found: list[tuple[str, Path, Path]] = []
    for key, city in cities.corpus().items():
        found.extend(tile_entries(key, city.ucdb_id))
    return found


ASSETS = ("app.html", "app.js")
# The results page is part of the walkthrough and ships beside it.
RESULT_FILES = ("result.html", "result.js")
# The hand-written pages GitHub Pages publishes. The walkthrough links them, so the bundle
# carries a copy and the links work from a local build too.
PAGES = ("model_pipeline.html", "proposal.html")
PAGES_DIR = Path(__file__).parent / "pages"


def publish_pages(destination: Path) -> list[Path]:
    """Copy the result files and the pages into the bundle. Returns the paths written."""
    dash = Path(__file__).parent / "dash"
    sources = [dash / name for name in RESULT_FILES] + [PAGES_DIR / name for name in PAGES]
    written = []
    for source in sources:
        target = destination / source.name
        target.write_text(source.read_text())
        written.append(target)
    return written


def write_walkthrough(destination: Path) -> None:
    """Write app.js and the stamped index.html, the page that reads the city data."""
    here = Path(__file__).parent / "dash"
    # The page ships beside its data so the bundle stays a self-contained pile of files.
    script = (here / "app.js").read_text()
    (destination / "app.js").write_text(script)

    # Stamp the script reference with a hash of its contents. GitHub Pages serves assets
    # with max-age=600, so without this a returning visitor keeps running the previous
    # app.js for up to ten minutes after a republish and sees a page that no longer exists.
    digest = hashlib.sha256(script.encode()).hexdigest()[:10]
    page = (
        (here / "app.html")
        .read_text()
        .replace('<script src="app.js"></script>', f'<script src="app.js?v={digest}"></script>')
    )
    (destination / "index.html").write_text(page)


def build_bundle(destination: Path, data_root: Path = Path("data")) -> int:
    """Write the whole static bundle, including the page itself. Returns city count."""
    cities = discover()
    if not cities:
        console.print(
            "[red]No city has both a bundle and generated physics.[/] "
            "Run 'shadecast build <city>' then 'shadecast surrogate generate'."
        )
        raise typer.Exit(code=1)

    destination.mkdir(parents=True, exist_ok=True)
    with console.status("[cyan]building bundle[/]"):
        payload = build_index(cities, destination, data_root)

    write_walkthrough(destination)
    publish_pages(destination)

    size = sum(f.stat().st_size for f in destination.iterdir() if f.is_file())
    console.print(
        f"  [green]{len(payload['cities'])} cities[/], "
        f"{len(list(destination.iterdir()))} files, {size / 1e6:.1f} MB"
    )
    return len(payload["cities"])


@app.command("pages")
def pages(
    out: Annotated[Path, typer.Option("--out", help="Bundle directory.")] = DEFAULT_OUT,
) -> None:
    """Republish the pages and the walkthrough shell without rebuilding the city data.

    For a change to a page or to the walkthrough's markup, when the data files in the
    bundle are already current and rebuilding them would only take time.
    """
    out.mkdir(parents=True, exist_ok=True)
    write_walkthrough(out)
    written = publish_pages(out)
    console.print(f"[green]index.html and {len(written)} pages[/] written into {out}")


@app.command("build")
def build(
    out: Annotated[Path, typer.Option("--out", help="Bundle directory.")] = DEFAULT_OUT,
) -> None:
    """Build the static bundle without serving it.

    Point --out at docs/ to publish the walkthrough on GitHub Pages, which serves the
    bundle exactly as it is: the page is static files and does all its work in the
    browser, so nothing here needs a Python process at view time.
    """
    build_bundle(out)
    console.print(f"[green]built[/] into {out}")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    port: Annotated[int, typer.Option("--port", help="Port to serve on.")] = 8765,
    out: Annotated[Path | None, typer.Option("--out", help="Bundle directory.")] = None,
    rebuild: Annotated[bool, typer.Option("--rebuild", help="Regenerate the bundle.")] = False,
    open_browser: Annotated[bool, typer.Option("--open/--no-open")] = True,
) -> None:
    """Build the walkthrough bundle if needed, then serve it."""
    if ctx.invoked_subcommand is not None:
        return
    destination = out if out else DEFAULT_OUT
    if rebuild or not (destination / "index.json").exists():
        build_bundle(destination)

    console.print(f"[green]shadecast dash[/] on http://127.0.0.1:{port}/  (ctrl-c to stop)")
    serve(destination, port=port, open_browser=open_browser)
