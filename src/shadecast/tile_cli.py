"""Command line for tiles: list the 1 km cells of an urban centre and choose among them.

Every urban centre is an exact set of 1 km GHS grid cells, so listing its tiles is a
computation, not a choice. The city catalog answers every question asked here; this module
parses flags and renders answers. Choosing tiles is explicit: the densest, a spread across
built-fraction terciles, named ids, or a seeded draw. Selection writes nothing; building does.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from functools import partial
from typing import Annotated

import typer

from . import cities
from .console import (
    console,
    error_console,
    pairs_table,
    plans_table,
    stage_line,
    stages_reached,
    tiles_table,
)
from .corpus import tile_paths
from .corpus.tile_description import describe
from .corpus.tiling import select_densest, select_ids, select_random, select_stratified
from .corpus.urban_centres import UrbanCentres
from .service.city_catalog import CityCatalog
from .service.missing_stage import MissingStage
from .service.model_catalog import ModelCatalog
from .service.selection import Selection
from .service.tile_index import TileIndex
from .service.tile_report import TileReport
from .service.tile_reporter import TileReporter
from .service.tile_summary import TileSummary
from .service.unknown_city import UnknownCity
from .service.unknown_tile import UnknownTile

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="tile",
    help="List the 1 km tiles of an urban centre and choose which to build.",
    no_args_is_help=True,
)


def load_centres() -> UrbanCentres:
    return UrbanCentres.load()


def catalog() -> CityCatalog:
    """The catalog over the selection, the database and the tiles root, built per command.

    The database is loaded once here and handed to both the selection and the catalog.
    """
    centres = load_centres()
    selection = cities.corpus(centres=centres)
    models = ModelCatalog(tile_paths.MODELS_ROOT)
    return CityCatalog(Selection.resolved(selection), partial(_loaded, centres), _index(), models)


def _loaded(centres: UrbanCentres) -> UrbanCentres:
    return centres


def _index() -> TileIndex:
    return TileIndex(tile_paths.TILES_ROOT, describe)


def answer[Answer](ask: Callable[[], Answer]) -> Answer:
    """Ask the catalog one question; an unknown city or tile ends the command with its message."""
    try:
        return ask()
    except (UnknownCity, UnknownTile, MissingStage) as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc


@app.command("list")
def list_tiles(
    centre: Annotated[str, typer.Argument(help="A city key, an id, a slug or a name.")],
    limit: Annotated[int, typer.Option("--limit", help="Rows to show.")] = 20,
    refresh: Annotated[
        bool, typer.Option("--refresh", help="Describe again, ignoring tiles.json.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """List every tile of an urban centre, densest first, with the stages each has reached."""
    found = catalog()
    ask = partial(found.refresh, centre) if refresh else partial(found.tiles, centre)
    tiles = answer(ask)
    urban = found.centre(centre)
    if as_json:
        payload = {
            "urban_centre": {"id": urban.id, "slug": urban.slug, "name": urban.name},
            "count": len(tiles),
            "tiles": [tile.model_dump() for tile in tiles],
        }
        console.print_json(json.dumps(payload))
        return
    console.print(tiles_table(tiles[:limit]))
    console.print(
        f"[dim]{len(tiles)} tiles, {min(limit, len(tiles))} shown. "
        f"Written to {found.tiles_file(centre)}.[/]"
    )


@app.command("select")
def select(
    centre: Annotated[str, typer.Argument(help="A city key, an id, a slug or a name.")],
    densest: Annotated[int | None, typer.Option("--densest", help="The k densest tiles.")] = None,
    stratified: Annotated[
        int | None,
        typer.Option("--stratified", help="k tiles spread over built-fraction terciles."),
    ] = None,
    ids: Annotated[
        list[str] | None, typer.Option("--ids", help="Named tile ids, repeatable.")
    ] = None,
    random: Annotated[
        int | None, typer.Option("--random", help="k populated tiles drawn at random.")
    ] = None,
    seed: Annotated[int, typer.Option("--seed", help="Seed for --random.")] = 0,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """Choose tiles by one explicit rule. Prints the choice; building is a separate step."""
    strategies = [value for value in (densest, stratified, ids, random) if value]
    if len(strategies) != 1:
        raise typer.BadParameter("choose exactly one of --densest, --stratified, --ids or --random")
    tiles = answer(partial(catalog().tiles, centre))
    rows = [tile.model_dump() for tile in tiles]
    if densest:
        chosen = select_densest(rows, densest)
    elif stratified:
        chosen = select_stratified(rows, stratified)
    elif ids:
        chosen = _named(rows, ids)
    else:
        chosen = select_random(rows, int(random or 0), seed)
    if as_json:
        console.print_json(json.dumps(chosen))
        return
    console.print(tiles_table(_in_chosen_order(tiles, [str(row.get("id")) for row in chosen])))
    console.print(f"[dim]{len(chosen)} of {len(rows)} tiles chosen.[/]")


def _named(rows: list[dict], ids: list[str]) -> list[dict]:
    try:
        return select_ids(rows, ids)
    except KeyError as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc


def _in_chosen_order(tiles: list[TileSummary], chosen_ids: list[str]) -> list[TileSummary]:
    picked = [tile for tile in tiles if tile.id in chosen_ids]
    return sorted(picked, key=partial(_rank, chosen_ids))


def _rank(chosen_ids: list[str], tile: TileSummary) -> int:
    return chosen_ids.index(tile.id)


@app.command("stats")
def stats(
    centre: Annotated[str, typer.Argument(help="A city key, an id, a slug or a name.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of tables.")] = False,
) -> None:
    """Statistics over one urban centre's tiles: counts, people, spreads, and k of N per stage."""
    statistics = answer(partial(catalog().statistics, centre))
    if as_json:
        console.print_json(statistics.model_dump_json())
        return
    console.print(
        pairs_table(
            statistics.name,
            {
                "tiles": statistics.tiles,
                "populated tiles": statistics.populated_tiles,
                "people, 2020 epoch": statistics.population_2020,
                "people, 2025 epoch (GHS-UCDB)": statistics.population_2025,
                **statistics.tiles_over,
            },
        )
    )
    for field, quantiles in statistics.quantiles.items():
        console.print(pairs_table(field, quantiles))
    console.print(f"[dim]{stage_line(statistics.stages)}.[/]")


@app.command("show")
def show(
    centre: Annotated[str, typer.Argument(help="A city key, an id, a slug or a name.")],
    tile: Annotated[
        str | None,
        typer.Option("--tile", help="A tile id such as t43N_249_2547; else every tile on disk."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """Where everything for a tile lives, and which stages have run. Reads disk only."""
    found = catalog()
    if tile is None:
        listed = answer(partial(found.tiles_on_disk, centre))
    else:
        listed = [answer(partial(found.tile, centre, tile))]
    if as_json:
        console.print_json(json.dumps([item.model_dump() for item in listed]))
        return
    if not listed:
        console.print(f"[dim]no tile on disk for {centre}; run 'sdc build {centre}' first.[/]")
        return
    # One two-column table per tile: paths are long, so they read down, not across.
    for item in listed:
        console.print(
            pairs_table(
                f"{centre} {item.tile}",
                {
                    "bundle": item.bundle,
                    "surrogate": item.surrogate,
                    "results": item.results,
                    "stages run": stages_reached(item.stages),
                },
            )
        )
    if tile is None:
        console.print(
            f"[dim]{len(listed)} tile{'s' if len(listed) != 1 else ''} on disk for {centre}.[/]"
        )


@app.command("report")
def report(
    centre: Annotated[str, typer.Argument(help="A city key, an id, a slug or a name.")],
    tile: Annotated[
        str | None,
        typer.Option("--tile", help="A tile id; else the tile that has come furthest."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of tables.")] = False,
) -> None:
    """A tile's report: its facts, the baseline, the physics run and every scored plan."""
    reporter = TileReporter(catalog())
    ask = (
        partial(reporter.report, centre, tile)
        if tile
        else partial(reporter.report_furthest, centre)
    )
    found = answer(ask)
    if as_json:
        console.print_json(found.model_dump_json())
        return
    console.print(pairs_table(f"{found.name} {found.tile}", _fact_rows(found)))
    if found.baseline is None:
        console.print(
            f"[dim]no baseline physics yet; run 'sdc run {centre} --tile {found.tile}' first.[/]"
        )
        return
    console.print(
        pairs_table(
            "doing nothing",
            {"exposure, C": found.baseline.exposure, "people at risk": found.baseline.at_risk},
        )
    )
    if not found.plans:
        console.print(
            f"[dim]no plans yet; run 'sdc surrogate treeshade generate {centre} "
            f"--tiles {found.tile}' first.[/]"
        )
        return
    console.print(plans_table(found.plans))
    if found.physics is not None:
        console.print(
            f"[dim]{found.physics.designs} designs through the engine, "
            f"{found.physics.engine_minutes} engine minutes.[/]"
        )


def _fact_rows(found: TileReport) -> dict:
    facts = found.facts
    return {
        "city": facts.key,
        "design day": facts.design_day,
        "tier": facts.tier,
        "buildings": facts.buildings,
        "built fraction": facts.built_fraction,
        "canopy": facts.canopy,
        "people, 2020 epoch": facts.population_2020,
        "stages run": stages_reached(found.stages),
    }
