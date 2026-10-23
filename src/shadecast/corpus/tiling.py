"""Enumerate the tiles of an urban centre, describe them, and choose among them.

Attributes are computed for every tile before any is built, from rasters that share the GHS
grid: 2020 population and density from GHS-POP, built fraction and mean height from GHS-BUILT.
That is what makes a selection rule explicit, whether it asks for the densest tiles, a spread
across built-fraction terciles, named ids, or a seeded draw. Selection writes nothing;
building does.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep

from .tile import KM, Tile
from .tile_rasters import TileRasters

TERCILES = 3
SQUARE_METRES_PER_TILE = KM * KM


def _north_to_south(tile: Tile) -> tuple[int, int]:
    return -tile.y_km, tile.x_km


def tiles_of(polygon: BaseGeometry) -> list[Tile]:
    """Every 1 km cell whose centre lies inside the boundary, north to south, west to east."""
    minx, miny, maxx, maxy = polygon.bounds
    prepared = prep(polygon)
    found: list[Tile] = []
    for y_km in range(int(np.floor(miny / KM)), int(np.ceil(maxy / KM))):
        for x_km in range(int(np.floor(minx / KM)), int(np.ceil(maxx / KM))):
            tile = Tile(x_km, y_km)
            if prepared.contains(Point(*tile.centre_mollweide)):
                found.append(tile)
    return sorted(found, key=_north_to_south)


def _mean_height_where_built(rasters: TileRasters, tile: Tile) -> float:
    """Mean height over the cells that have any, so empty cells do not dilute it."""
    block = rasters.building_height.block(tile.bounds)
    built = block[block > 0]
    return float(built.mean()) if built.size else 0.0


def describe_tile(tile: Tile, rasters: TileRasters) -> dict:
    """One record: people, density, built fraction, mean height, and both bounds."""
    people = rasters.population_2020.sum_in(tile.bounds)
    lat, lon = tile.centre_wgs84
    return {
        "id": tile.id,
        "x_km": tile.x_km,
        "y_km": tile.y_km,
        "population_2020": round(people, 1),
        "density_2020_per_km2": round(people, 1),
        "built_fraction": round(
            rasters.built_surface.sum_in(tile.bounds) / SQUARE_METRES_PER_TILE, 4
        ),
        "mean_height_m": round(_mean_height_where_built(rasters, tile), 2),
        "bounds_mollweide": list(tile.bounds),
        "bounds_wgs84": [round(value, 6) for value in tile.bounds_wgs84],
        "centre": [round(lat, 6), round(lon, 6)],
    }


def attributes(tiles: Sequence[Tile], rasters: TileRasters) -> list[dict]:
    return [describe_tile(tile, rasters) for tile in tiles]


def _density(row: dict) -> float:
    return float(row.get("density_2020_per_km2", 0.0))


def _built_fraction(row: dict) -> float:
    return float(row.get("built_fraction", 0.0))


def select_densest(rows: Iterable[dict], count: int) -> list[dict]:
    return sorted(rows, key=_density, reverse=True)[:count]


def select_stratified(rows: Iterable[dict], count: int) -> list[dict]:
    """The densest tile of each built-fraction tercile in turn, highest tercile first."""
    by_built = sorted(rows, key=_built_fraction, reverse=True)
    if not by_built:
        return []
    parts = np.array_split(np.array(by_built, dtype=object), TERCILES)
    queues = [sorted(part, key=_density, reverse=True) for part in parts]
    chosen: list[dict] = []
    turn = 0
    while len(chosen) < count and any(queues):
        queue = queues[turn % TERCILES]
        if queue:
            chosen.append(queue.pop(0))
        turn += 1
    return chosen


def select_ids(rows: Iterable[dict], ids: Sequence[str]) -> list[dict]:
    by_id = {str(row.get("id")): row for row in rows}
    chosen: list[dict] = []
    for tile_id in ids:
        row = by_id.get(tile_id)
        if row is None:
            raise KeyError(f"no tile {tile_id!r} in this urban centre")
        chosen.append(row)
    return chosen


def select_random(rows: Iterable[dict], count: int, seed: int) -> list[dict]:
    """A seeded draw among the tiles where anyone lives.

    Three arguments because a draw is defined by its candidates, its size and its seed.
    """
    populated = [row for row in rows if float(row.get("population_2020", 0.0)) > 0]
    rng = np.random.default_rng(seed)
    picked = rng.choice(len(populated), size=min(count, len(populated)), replace=False)
    return [populated[int(index)] for index in picked]
