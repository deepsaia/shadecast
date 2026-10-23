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

from .console import console, error_console, tiles_table
from .corpus import ucdb
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
from .data.built import building_height, built_surface
from .data.ghs_product import read_window
from .data.population import GHS_POP

logger = logging.getLogger(__name__)

TILES_ROOT = Path("data/tiles")

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
    population, origin = read_window(GHS_POP, polygon.bounds)
    built, _ = built_surface(polygon.bounds)
    height, _ = building_height(polygon.bounds)
    logger.info("%s: %d tiles described", centre.slug, len(tiles))
    return attributes(tiles, population, built, height, origin)


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


def load_or_describe(centre: UrbanCentre, refresh: bool) -> dict:
    path = tiles_path(centre)
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    return write_tiles(centre, describe(centre))


def _resolve(text: str) -> UrbanCentre:
    try:
        return load_centres().resolve(text)
    except (KeyError, ValueError) as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc


def _by_density(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: -float(row.get("density_per_km2", 0.0)))


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
    payload = load_or_describe(found, refresh)
    rows = _by_density(payload.get("tiles", []))
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
    rows = load_or_describe(found, refresh=False).get("tiles", [])
    try:
        if densest:
            chosen = select_densest(rows, densest)
        elif stratified:
            chosen = select_stratified(rows, stratified)
        elif ids:
            chosen = select_ids(rows, ids)
        else:
            chosen = select_random(rows, int(random or 0), seed=seed)
    except KeyError as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    if as_json:
        console.print_json(json.dumps(chosen))
        return
    console.print(tiles_table(chosen))
    console.print(f"[dim]{len(chosen)} of {len(rows)} tiles chosen.[/]")
