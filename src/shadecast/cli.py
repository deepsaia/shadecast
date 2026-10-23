"""shadecast command line.

Built on Typer so that help, completion and error reporting come for free, and on
rich so that corpus and result tables stay readable as they grow.

Machine-readable output goes to stdout via ``--json`` on the commands that produce
results; human output and logs go to the console and stderr respectively, so a
benchmark run can be piped into an aggregator without stripping decoration.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Annotated

import click
import typer

from . import cities, tile_cli
from .console import add_build_row, build_table, console, corpus_table, error_console, result_table
from .corpus import tile_paths
from .corpus.tile_paths import TilePaths
from .corpus_cli import app as corpus_app
from .dash_cli import app as dash_app
from .experiments_cli import app as experiments_app
from .logging_setup import configure
from .pipeline import evaluate
from .sim.runner import run as run_engine
from .surrogate_cli import app as surrogate_app
from .tile_build import build_tile
from .tile_cli import app as tile_app

logger = logging.getLogger("shadecast")

app = typer.Typer(
    name="shadecast",
    help="Turn any city into an urban heat decision problem, from open data.",
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def entry() -> int:
    """Console entry point. Ctrl-C ends any command with one line and exit code 130.

    Click's own handling would print "Aborted!" and exit 1; a stop is not an error, and
    every long command has already said how to resume by the time it gets here.
    """
    try:
        app(standalone_mode=False)
    except click.exceptions.Exit as exit_:  # typer.Exit, raised on purpose by a command
        return int(exit_.exit_code)
    except click.ClickException as error:  # usage errors, bad parameters
        error.show()
        return int(error.exit_code)
    except (KeyboardInterrupt, click.exceptions.Abort):
        error_console.print("\nstopped")
        return 130
    return 0


app.add_typer(corpus_app, name="corpus")
app.add_typer(tile_app, name="tile")
app.add_typer(surrogate_app, name="surrogate")
app.add_typer(dash_app, name="dash")
app.add_typer(experiments_app, name="experiments")


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug logging.")] = False,
) -> None:
    """Configure logging before any command runs."""
    configure(verbose=verbose)


@app.command("list")
def list_cities(
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """Show the city corpus and how it is stratified."""
    corpus = cities.corpus()
    if as_json:
        payload = {
            "summary": cities.summary(corpus.values()),
            "cities": [vars(c) for c in corpus.values()],
        }
        console.print_json(json.dumps(payload))
        return

    stats = cities.summary(corpus.values())
    console.print(corpus_table(list(corpus.values())))
    console.print(
        f"\n[dim]{stats['cities']} cities, {stats['global_south']} Global South, "
        f"{stats['tropical_A']} tropical, {stats['southern_hemisphere']} southern hemisphere, "
        f"{stats['wri_overlap']} overlapping WRI Cool Cities Lab.[/]"
    )


@app.command()
def build(
    city: Annotated[
        str | None, typer.Argument(help="Selection key, for example ahmedabad.")
    ] = None,
    build_all: Annotated[bool, typer.Option("--all", help="Build every selected city.")] = False,
    tiles: Annotated[
        str | None,
        typer.Option(
            "--tiles",
            help="Tile ids separated by commas, or 'all' for every tile. Default: the densest.",
        ),
    ] = None,
    densest: Annotated[
        int | None, typer.Option("--densest", help="The K tiles with most residents.")
    ] = None,
    stratified: Annotated[
        int | None,
        typer.Option("--stratified", help="K tiles spread over built-fraction terciles."),
    ] = None,
) -> None:
    """Assemble tile bundles from open sources into the tile layout. No credentials needed.

    One tile per city by default, the one with most residents. --tiles names tiles or asks
    for all of them; --densest and --stratified pick K the way the corpus selection does.
    """
    if not build_all and city is None:
        raise typer.BadParameter("give a city key or use --all")
    named = tiles is not None and tiles.strip().lower() not in ("", tile_cli.ALL_TILES)
    if named and build_all:
        raise typer.BadParameter("named --tiles apply to one city")
    corpus = cities.corpus()
    keys = list(corpus) if build_all else [str(city)]
    unknown = [key for key in keys if key not in corpus]
    if unknown:
        raise typer.BadParameter(f"unknown city keys {unknown}, try 'shadecast list'")

    centres = tile_cli.load_centres()
    table = build_table()
    failed: list[str] = []
    with console.status("[cyan]assembling bundles[/]") as status:
        for key in keys:
            selected = corpus.get(key)
            if selected is None:
                continue
            centre = centres.by_id(selected.ucdb_id)
            targets = tile_cli.chosen_tiles(centre, tiles, densest, stratified)
            for target in targets:
                status.update(f"[cyan]{key} {target.id}[/]: pulling open layers")
                started = time.time()
                try:
                    provenance = build_tile(
                        selected, target, TilePaths(tile_paths.TILES_ROOT, centre.id, target)
                    )
                # One unreachable source must not abandon the remaining tiles. The
                # failure is logged with its type and never swallowed, and the command
                # exits non-zero.
                except Exception:
                    logger.exception(
                        "build failed for %s %s after %.1fs",
                        key,
                        target.id,
                        time.time() - started,
                    )
                    failed.append(f"{key} {target.id}")
                    continue
                add_build_row(table, f"{key} {target.id}", time.time() - started, provenance)
                built = TilePaths(tile_paths.TILES_ROOT, centre.id, target)
                pick = "" if len(targets) == 1 else f" --tiles {target.id}"
                console.print(
                    f"[green]{key}[/] {target.id}: bundle at {built.bundle}\n"
                    f"  next: sdc surrogate generate {key}{pick} --jobs 4"
                )
            console.print(
                f"[dim]{key}: {len(targets)} of {tile_cli.tile_count(centre)} tiles chosen.[/]"
            )

    console.print(table)
    if failed:
        error_console.print(f"[red]{len(failed)} failed:[/] {', '.join(failed)}")
        raise typer.Exit(code=1)


@app.command()
def plan(
    bundle: Annotated[Path, typer.Argument(help="A built city bundle directory.")],
    kind: Annotated[str, typer.Option("--kind", help="Intervention type.")] = "tree",
    budget: Annotated[float, typer.Option("--budget", help="Budget in USD.")] = 10_000_000,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """Plan an intervention over a bundle and score it against doing nothing."""
    with console.status(f"[cyan]{bundle.name}[/]: baseline physics, then the plan"):
        result = evaluate(bundle, kind=kind, budget_usd=budget)

    if as_json:
        console.print_json(json.dumps(result))
        return
    console.print(result_table(result))
    console.print(
        f"[dim]engine {result['engine_seconds']['baseline']:.0f}s baseline, "
        f"{result['engine_seconds']['plan']:.0f}s plan, tier {result['tier']}.[/]"
    )


@app.command()
def run(
    bundle: Annotated[Path, typer.Argument(help="A built city bundle directory.")],
    date: Annotated[str, typer.Argument(help="Design day, YYYY-MM-DD.")],
) -> None:
    """Run the physics engine over a bundle. The engine is a separate subprocess."""
    with console.status(f"[cyan]{bundle.name}[/]: running the engine"):
        result = run_engine(bundle, date)
    console.print_json(json.dumps(result.as_dict()))


if __name__ == "__main__":
    app()
