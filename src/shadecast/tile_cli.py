"""Command line for tiles: list the 1 km cells of an urban centre and choose among them.

Every urban centre is an exact set of 1 km GHS grid cells, so listing its tiles is a
computation, not a choice. Each tile is described from rasters that share the grid before any
bundle exists, and the description is written beside the urban centre's tiles so that a later
status report can say k of N. Choosing tiles is explicit: the densest, a spread across
built-fraction terciles, named ids, or a seeded draw. Selection writes nothing; building does.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer
from shapely.geometry.base import BaseGeometry

from . import cities
from .console import console, error_console, pairs_table, records_table, tiles_table
from .corpus import migrate, ucdb
from .corpus.legacy_city import LegacyCity
from .corpus.migration import Migration
from .corpus.statistics import tile_stats
from .corpus.tile import Tile
from .corpus.tile_paths import TILES_ROOT, TilePaths
from .corpus.tile_rasters import TileRasters
from .corpus.tiling import (
    attributes,
    select_densest,
    select_ids,
    select_random,
    select_stratified,
    tiles_of,
)
from .corpus.urban_centre import UrbanCentre
from .corpus.urban_centres import UrbanCentres

logger = logging.getLogger(__name__)

# Where bundles and physics lived before tiles, for the migration.
LEGACY_BUNDLE_ROOTS = (Path("out/corpus"), Path("data/cities"))
LEGACY_SURROGATE_ROOT = Path("data/surrogate")

app = typer.Typer(
    name="tile",
    help="List the 1 km tiles of an urban centre and choose which to build.",
    no_args_is_help=True,
)


def load_centres() -> UrbanCentres:
    return UrbanCentres.load()


def boundary(centre: UrbanCentre) -> BaseGeometry:
    """The urban centre polygon in World Mollweide, an exact union of 1 km cells."""
    polygons = ucdb.polygons()
    match = polygons.loc[polygons[ucdb.ID] == centre.id, "geometry"]
    if match.empty:
        raise KeyError(f"no boundary for urban centre {centre.id}")
    return match.iloc[0]


def describe(centre: UrbanCentre) -> list[dict]:
    """Every tile of the centre with population, density, built fraction and height."""
    polygon = boundary(centre)
    tiles = tiles_of(polygon)
    rows = attributes(tiles, TileRasters.read(polygon.bounds))
    logger.info("%s: %d tiles described", centre.slug, len(tiles))
    return rows


def tiles_path(centre: UrbanCentre) -> Path:
    return Path(TILES_ROOT) / str(centre.id) / "tiles.json"


def write_tiles(centre: UrbanCentre, rows: list[dict]) -> dict:
    payload = {
        "urban_centre": {
            "id": centre.id,
            "slug": centre.slug,
            "name": centre.name,
            "country": centre.country,
            "area_km2": centre.area_km2,
        },
        "release": f"{ucdb.RELEASE} {ucdb.VERSION}",
        "count": len(rows),
        "tiles": rows,
    }
    path = tiles_path(centre)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return payload


def cached_tiles(centre: UrbanCentre) -> dict | None:
    """The tiles written earlier for this centre, or None when there are none yet."""
    path = tiles_path(centre)
    return json.loads(path.read_text()) if path.exists() else None


def describe_and_write(centre: UrbanCentre) -> dict:
    return write_tiles(centre, describe(centre))


def _resolve(text: str) -> UrbanCentre:
    try:
        return load_centres().resolve(text)
    except (KeyError, ValueError) as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc


def _named(rows: list[dict], ids: list[str]) -> list[dict]:
    try:
        return select_ids(rows, ids)
    except KeyError as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc


@app.command("list")
def list_tiles(
    centre: Annotated[str, typer.Argument(help="An id, a slug such as ahmedabad, or a name.")],
    limit: Annotated[int, typer.Option("--limit", help="Rows to show.")] = 20,
    refresh: Annotated[
        bool, typer.Option("--refresh", help="Describe again, ignoring tiles.json.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """List every tile of an urban centre, densest first, and write tiles.json beside it."""
    found = _resolve(centre)
    payload = None if refresh else cached_tiles(found)
    if payload is None:
        payload = describe_and_write(found)
    rows = select_densest(payload.get("tiles", []), len(payload.get("tiles", [])))
    if as_json:
        console.print_json(json.dumps({**payload, "tiles": rows}))
        return
    console.print(tiles_table(rows[:limit]))
    console.print(
        f"[dim]{len(rows)} tiles, {min(limit, len(rows))} shown. Written to {tiles_path(found)}.[/]"
    )


@app.command("select")
def select(
    centre: Annotated[str, typer.Argument(help="An id, a slug such as ahmedabad, or a name.")],
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
    found = _resolve(centre)
    payload = cached_tiles(found) or describe_and_write(found)
    rows = payload.get("tiles", [])
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
    console.print(tiles_table(chosen))
    console.print(f"[dim]{len(chosen)} of {len(rows)} tiles chosen.[/]")


@app.command("stats")
def stats(
    centre: Annotated[str, typer.Argument(help="An id, a slug such as ahmedabad, or a name.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of tables.")] = False,
) -> None:
    """Statistics over the tiles of one urban centre: counts, people, and spreads."""
    found = _resolve(centre)
    payload = cached_tiles(found) or describe_and_write(found)
    summary = tile_stats(payload.get("tiles", []))
    summary["urban_centre"] = {
        "id": found.id,
        "slug": found.slug,
        "name": found.name,
        "population_2025": found.population_2025,
        "area_km2": found.area_km2,
    }
    if as_json:
        console.print_json(json.dumps(summary))
        return
    console.print(
        pairs_table(
            found.name,
            {
                "tiles": summary.get("tiles"),
                "populated tiles": summary.get("populated_tiles"),
                "people, 2020 epoch": summary.get("population_2020"),
                "people, 2025 epoch (GHS-UCDB)": found.population_2025,
                **summary.get("tiles_over", {}),
            },
        )
    )
    for field, quantiles in summary.get("quantiles", {}).items():
        console.print(pairs_table(field, quantiles))


def _tile(text: str) -> Tile:
    try:
        return Tile.from_id(text)
    except ValueError as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc


@app.command("path")
def path(
    centre: Annotated[str, typer.Argument(help="An id, a slug such as ahmedabad, or a name.")],
    tile: Annotated[str, typer.Argument(help="A tile id such as t6908_2816.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """Where everything for one tile lives, and which stages have run."""
    paths = TilePaths(TILES_ROOT, _resolve(centre).id, _tile(tile))
    listed = {**paths.as_dict(), "stages": paths.stages()}
    if as_json:
        console.print_json(json.dumps(listed))
        return
    console.print(pairs_table(f"{paths.urban_centre} {paths.tile.id}", paths.as_dict()))
    console.print(pairs_table("stages", paths.stages()))


def legacy_bundle(key: str) -> Path | None:
    """The bundle a city has under the pre-tile roots, if any."""
    for root in LEGACY_BUNDLE_ROOTS:
        candidate = Path(root) / key
        if (candidate / "provenance.json").exists():
            return candidate
    return None


def migrations() -> list[Migration]:
    """A migration for every selected city that still has a legacy bundle."""
    planned: list[Migration] = []
    for city in cities.corpus().values():
        bundle = legacy_bundle(city.key)
        if bundle is None:
            continue
        legacy = LegacyCity(city, bundle, Path(LEGACY_SURROGATE_ROOT) / city.key)
        paths = TilePaths(TILES_ROOT, city.ucdb_id, migrate.tile_of_bundle(bundle))
        planned.append(migrate.plan(legacy, paths))
    return planned


def _moves_table(planned: list[Migration]) -> list[dict]:
    return [
        {"what": move.label, "from": str(move.source), "to": str(move.target)}
        for migration in planned
        for move in migration
    ]


@app.command("migrate")
def migrate_legacy(
    apply: Annotated[
        bool, typer.Option("--apply", help="Move the directories. Without it, only show the plan.")
    ] = False,
) -> None:
    """Move bundles and physics built before tiles into the tile layout, without re-running any.

    Shows the plan and stops unless --apply is given. Refuses while a generator holds a lock
    on anything about to move, and never overwrites an existing tile directory.
    """
    planned = migrations()
    if not planned:
        console.print("[dim]nothing left in the legacy layout.[/]")
        return
    console.print(records_table("Planned moves", _moves_table(planned)))
    if not apply:
        console.print("[dim]Plan only. Add --apply to move.[/]")
        return
    locks = migrate.held_locks(planned)
    if locks:
        error_console.print(
            "a generator holds "
            + ", ".join(str(lock) for lock in locks)
            + "; try again when it has finished",
            style="red",
            markup=False,
        )
        raise typer.Exit(code=1)
    for migration in planned:
        migrate.apply(migration)
        console.print(f"[green]{migration.paths.urban_centre}[/] {migration.paths.tile.id}: moved")
