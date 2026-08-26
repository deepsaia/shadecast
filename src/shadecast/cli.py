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

import typer

from .build import build_city
from .cities import CORPUS, summary
from .console import add_build_row, build_table, console, corpus_table, error_console, result_table
from .logging_setup import configure
from .pipeline import evaluate
from .sim.runner import run as run_engine

logger = logging.getLogger("shadecast")

DEFAULT_OUT = Path("data/cities")

app = typer.Typer(
    name="shadecast",
    help="Turn any city into an urban heat decision problem, from open data.",
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


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
    if as_json:
        payload = {"summary": summary(), "cities": [vars(c) for c in CORPUS.values()]}
        console.print_json(json.dumps(payload))
        return

    stats = summary()
    console.print(corpus_table(list(CORPUS.values())))
    console.print(
        f"\n[dim]{stats['cities']} cities, {stats['global_south']} Global South, "
        f"{stats['tropical_A']} tropical, {stats['southern_hemisphere']} southern hemisphere, "
        f"{stats['wri_overlap']} overlapping WRI Cool Cities Lab.[/]"
    )


@app.command()
def build(
    city: Annotated[str | None, typer.Argument(help="Corpus key, for example ahmedabad.")] = None,
    build_all: Annotated[bool, typer.Option("--all", help="Build the whole corpus.")] = False,
    out: Annotated[Path | None, typer.Option("--out", help="Output root.")] = None,
    side: Annotated[int, typer.Option("--side", help="Study area side in metres.")] = 1000,
    res: Annotated[float, typer.Option("--res", help="Grid resolution in metres.")] = 1.0,
) -> None:
    """Assemble city bundles from open sources. No account, key or quota needed."""
    if not build_all and city is None:
        raise typer.BadParameter("give a city key or use --all")

    keys = list(CORPUS) if build_all else [str(city)]
    unknown = [key for key in keys if key not in CORPUS]
    if unknown:
        raise typer.BadParameter(f"unknown city keys {unknown}, try 'shadecast list'")

    root = out if out else DEFAULT_OUT
    table = build_table()
    failed: list[str] = []

    with console.status("[cyan]assembling bundles[/]") as status:
        for key in keys:
            status.update(f"[cyan]{key}[/]: pulling open layers")
            started = time.time()
            try:
                provenance = build_city(CORPUS[key], root / key, side_m=side, res_m=res)
            # One unreachable source must not abandon the remaining cities. The
            # failure is logged with its type and never swallowed, and the command
            # exits non-zero.
            except Exception:
                logger.exception("build failed for %s after %.1fs", key, time.time() - started)
                failed.append(key)
                continue
            add_build_row(table, key, time.time() - started, provenance)

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
