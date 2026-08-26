"""Command line for the local dashboard.

Builds a static bundle then serves it from the standard library. No web framework,
no build step, no CDN: the bundle is plain files, so it can be zipped, archived or
served anywhere, which matters for reproducing a result years later.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

from .cities import CORPUS
from .console import console
from .dash.builder import build_index
from .dash.server import serve

logger = logging.getLogger(__name__)

# out/corpus first, deliberately. The corpus is what the experiments and the surrogate
# baselines are built from, and a stale bundle under data/cities once made the page
# describe one city's geometry beside another one's physics.
BUNDLE_ROOTS = (Path("out/corpus"), Path("data/cities"))
# The same directory that gets published. Serving the walkthrough locally from one
# bundle and publishing another is how the two quietly drift apart, which is exactly
# what happened once: `shadecast dash` kept showing a build from hours earlier while
# the public page had moved on.
DEFAULT_OUT = Path("docs")

app = typer.Typer(name="dash", help="Interactive local walkthrough of what we do to a city.")


def find_bundle(city: str) -> Path | None:
    """Locate the bundle the physics was actually run on."""
    found = [r / city for r in BUNDLE_ROOTS if (r / city / "provenance.json").exists()]
    if len(found) > 1:
        logger.warning("%s has %d bundles; using %s", city, len(found), found[0])
    return found[0] if found else None


def discover() -> list[tuple[str, Path, Path]]:
    """Every city that has both a bundle and generated physics."""
    found = []
    for city in CORPUS:
        surrogate_dir = Path("data/surrogate") / city
        bundle = find_bundle(city)
        if bundle and (surrogate_dir / "baseline" / "tmrt_daylight.npy").exists():
            found.append((city, bundle, surrogate_dir))
    return found


ASSETS = ("app.html", "app.js")


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

    here = Path(__file__).parent / "dash"
    # The page ships beside its data so the bundle stays a self-contained pile of files.
    (destination / "index.html").write_text((here / "app.html").read_text())
    (destination / "app.js").write_text((here / "app.js").read_text())

    size = sum(f.stat().st_size for f in destination.iterdir() if f.is_file())
    console.print(
        f"  [green]{len(payload['cities'])} cities[/], "
        f"{len(list(destination.iterdir()))} files, {size / 1e6:.1f} MB"
    )
    return len(payload["cities"])


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
