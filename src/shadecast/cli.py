"""shadecast command line.

Built on Typer so that help, completion and error reporting come for free, and on
rich so that corpus and result tables stay readable as they grow.

Machine-readable output goes to stdout via ``--json`` on the commands that produce
results; human output and logs go to the console and stderr respectively, so a
run over many tiles can be piped into an aggregator without stripping decoration.

The service a command runs is imported inside the command. At the top of the module it
would load torch, geopandas and rasterio before the arguments are parsed, and ``sdc --help``
would take seconds instead of a fraction of one. ``tests/test_startup.py`` guards this.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

import click
import typer

from . import tile_cli
from .build_progress import BuildProgress
from .console import console
from .console import corpus_table
from .console import error_console
from .console import ranking_table
from .console import result_table
from .console import runs_table
from .console import scenario_table
from .corpus import tile_paths
from .corpus_cli import app as corpus_app
from .exit_codes import FAILED
from .exit_codes import STOPPED
from .exit_codes import fail
from .experiments_cli import app as experiments_app
from .logging_setup import configure
from .serve_cli import serve
from .service.build_request import BuildRequest
from .service.missing_stage import MissingStage
from .service.null_progress import NullProgress
from .service.plan_request import PlanRequest
from .service.scenario import Scenario
from .service.unknown_city import UnknownCity
from .service.unknown_tile import UnknownTile
from .simulate_cli import app as simulate_app
from .surrogate_cli import app as surrogate_app
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
        returned = app(standalone_mode=False)
    except click.exceptions.Exit as exit_:  # typer.Exit, raised on purpose by a command
        return int(exit_.exit_code)
    except click.ClickException as error:  # usage errors, bad parameters
        error.show()
        return int(error.exit_code)
    except (KeyboardInterrupt, click.exceptions.Abort):
        error_console.print("\nstopped")
        return STOPPED
    # Outside standalone mode click hands a planned exit's code back instead of raising it.
    return int(returned) if isinstance(returned, int) else 0


app.add_typer(corpus_app, name="corpus")
app.add_typer(tile_app, name="tile")
app.add_typer(simulate_app, name="simulate")
app.add_typer(surrogate_app, name="surrogate")
app.add_typer(experiments_app, name="experiments")
app.command("serve")(serve)


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", help="Debug logging.")] = False,
) -> None:
    """Configure logging before any command runs."""
    configure(verbose=verbose)


@app.command("cities")
def list_cities(
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """Show the selected cities, how they are stratified, and what each has on disk."""
    from . import cities
    from .service.city_catalog import CityCatalog

    selection = cities.corpus()
    listed = CityCatalog.over(selection, tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT).cities()
    summary = cities.summary(selection.values())
    if as_json:
        payload = {"summary": summary, "cities": [city.model_dump() for city in listed]}
        console.print_json(json.dumps(payload))
        return
    console.print(corpus_table(listed))
    console.print(
        f"\n[dim]{summary.get('cities')} cities, {summary.get('global_south')} Global South, "
        f"{summary.get('tropical_A')} tropical, {summary.get('southern_hemisphere')} southern "
        f"hemisphere, {summary.get('wri_overlap')} overlapping WRI Cool Cities Lab.[/]"
    )


@app.command("results")
def results(
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of tables.")] = False,
) -> None:
    """The measured results across every tile with physics: ranking, arrangement verdict, totals."""
    from .service.city_catalog import CityCatalog
    from .service.results_report import ResultsReport

    catalog = CityCatalog.open(tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT)
    found = ResultsReport(catalog, tile_paths.TILES_ROOT.parent).collect()
    if as_json:
        console.print_json(found.model_dump_json())
        return
    if not found.cities:
        console.print("[dim]no tile with physics yet; run 'sdc simulate treeshade <city>' first.[/]")
        return
    console.print(ranking_table(found.ranking.rows))
    verdict = found.arrangement
    if verdict.cities_compared:
        console.print(
            f"Scattered planting beat clustered per dollar at matched coverage in "
            f"{verdict.scattered_wins} of {verdict.cities_compared} tiles, "
            f"by {verdict.ratio_min} to {verdict.ratio_max} times."
        )
    totals = found.totals
    console.print(
        f"[dim]{totals.cities} tiles, {totals.plans} plans, budgets {totals.budget_min_m} to "
        f"{totals.budget_max_m} million.[/]"
    )


@app.command("runs")
def runs(
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """What is simulating or training right now, and whether its process is still alive."""
    from .service.city_catalog import CityCatalog
    from .service.run_status import RunStatus

    found = RunStatus(CityCatalog.open(tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT), tile_paths.MODELS_ROOT).runs()
    if as_json:
        console.print_json(json.dumps([run.model_dump() for run in found]))
        return
    if not found:
        console.print("[dim]nothing is running: no simulation lock and no unfinished training.[/]")
        return
    console.print(runs_table(found))


@app.command()
def build(
    city: Annotated[str | None, typer.Argument(help="Selection key, for example ahmedabad.")] = None,
    build_all: Annotated[bool, typer.Option("--all", help="Build every selected city.")] = False,
    tiles: Annotated[
        str | None,
        typer.Option(
            "--tiles",
            help="Tile ids separated by commas, or 'all' for every tile. Default: the densest.",
        ),
    ] = None,
    densest: Annotated[int | None, typer.Option("--densest", help="The K tiles with most residents.")] = None,
    stratified: Annotated[
        int | None,
        typer.Option("--stratified", help="K tiles spread over built-fraction terciles."),
    ] = None,
) -> None:
    """Assemble tile bundles from open sources into the tile layout. No credentials needed.

    One tile per city by default, the one with most residents. --tiles names tiles or asks
    for all of them; --densest and --stratified pick K the way the corpus selection does.
    """
    from .service.build_service import BuildService
    from .tile_build import build_tile

    request = BuildRequest(city=city, build_all=build_all, tiles=tiles, densest=densest, stratified=stratified)
    service = BuildService(tile_cli.catalog(), tile_paths.TILES_ROOT, build_tile)
    try:
        outcome = service.build(request, BuildProgress(console))
    except (ValueError, UnknownCity, UnknownTile) as exc:
        fail(exc)
    for key, chosen in outcome.chosen.items():
        console.print(f"[dim]{key}: {chosen} of {outcome.totals.get(key, 0)} tiles chosen.[/]")
    if outcome.failed:
        error_console.print(f"[red]{len(outcome.failed)} failed:[/] {', '.join(outcome.failed)}")
        raise typer.Exit(code=FAILED)


@app.command()
def plan(
    city: Annotated[str, typer.Argument(help="A city key, an id, a slug or a name.")],
    tile: Annotated[str | None, typer.Option("--tile", help="A tile id; else the densest built tile.")] = None,
    kind: Annotated[str, typer.Option("--kind", help="Intervention type.")] = "tree",
    budget: Annotated[float, typer.Option("--budget", help="Budget in USD.")] = 10_000_000,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """Plan an intervention over a tile and score it against doing nothing."""
    from .service.city_catalog import CityCatalog
    from .service.plan_service import PlanService

    service = PlanService(CityCatalog.open(tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT))
    request = PlanRequest(target=city, tile=tile, kind=kind, budget_usd=budget)
    try:
        with console.status(f"[cyan]{city}[/]: baseline physics, then the plan"):
            outcome = service.plan(request, NullProgress())
    except (UnknownCity, UnknownTile, MissingStage) as exc:
        fail(exc)
    if as_json:
        console.print_json(outcome.model_dump_json())
        return
    console.print(result_table(outcome.result))
    seconds = outcome.result.get("engine_seconds", {})
    console.print(
        f"[dim]engine {float(seconds.get('baseline', 0.0)):.0f}s baseline, "
        f"{float(seconds.get('plan', 0.0)):.0f}s plan, tier {outcome.result.get('tier')}.[/]"
    )


@app.command()
def scenario(
    city: Annotated[str, typer.Argument(help="A city key, an id, a slug or a name.")],
    tile: Annotated[str | None, typer.Option("--tile", help="A tile id; else the densest built tile.")] = None,
    kind: Annotated[str, typer.Option("--kind", help="Intervention kind; tree is the one with a surrogate.")] = "tree",
    arrangement: Annotated[
        str, typer.Option("--arrangement", help="How the trees are laid out: clustered, scattered or corridor.")
    ] = "clustered",
    coverage: Annotated[
        float | None, typer.Option("--coverage", help="Share of the feasible ground planted, above 0 and at most 1.")
    ] = None,
    budget: Annotated[
        float | None, typer.Option("--budget", help="Budget in USD; sets the coverage through the cost table.")
    ] = None,
    unit_cost: Annotated[
        float | None, typer.Option("--unit-cost", help="USD per square metre; the catalogue's price when absent.")
    ] = None,
    maintenance: Annotated[
        float | None,
        typer.Option("--maintenance", help="Yearly maintenance as a share of capital; the catalogue's when absent."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """Move the levers on a tile and read the outcomes from its surrogate, against doing nothing.

    Give --coverage or --budget, not both. The engine is never run; `sdc plan` is the slow, verified answer.
    """
    from .service.city_catalog import CityCatalog
    from .service.model_catalog import ModelCatalog
    from .service.scenario_service import ScenarioService

    models = ModelCatalog(tile_paths.MODELS_ROOT)
    service = ScenarioService(CityCatalog.open(tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT), models)
    try:
        asked = Scenario(
            target=city,
            tile=tile,
            kind=kind,
            arrangement=arrangement,
            coverage=coverage,
            budget_usd=budget,
            unit_cost=unit_cost,
            maintenance=maintenance,
        )
        with console.status(f"[cyan]{city}[/]: the surrogate over the tile"):
            outcome = service.evaluate(asked).outcome
    except (ValueError, LookupError) as exc:
        fail(exc)
    if as_json:
        console.print_json(outcome.model_dump_json())
        return
    console.print(scenario_table(outcome))


if __name__ == "__main__":
    app()
