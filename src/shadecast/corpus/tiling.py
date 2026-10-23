"""Enumerate the tiles of an urban centre, describe them, and choose among them.

Attributes are computed for every tile before any is built, from rasters that share the GHS
grid: population and density from GHS-POP, built fraction and mean height from GHS-BUILT. That
is what makes a selection rule explicit, whether it asks for the densest tiles, a spread across
built-fraction terciles, named ids, or a seeded draw. Selection writes nothing; building does.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep

from ..data import ghs_grid
from .tile import KM, Tile

CELLS_PER_SIDE = int(KM / ghs_grid.CELL_M)
TERCILES = 3


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
    return sorted(found, key=lambda tile: (-tile.y_km, tile.x_km))


def _block(field: np.ndarray, origin: tuple[float, float], tile: Tile) -> np.ndarray:
    """The 10 by 10 cells of a 100 m field that fall inside one tile."""
    minx, _, _, maxy = tile.bounds
    row0 = round((origin[1] - maxy) / ghs_grid.CELL_M)
    col0 = round((minx - origin[0]) / ghs_grid.CELL_M)
    rows = slice(max(row0, 0), max(row0 + CELLS_PER_SIDE, 0))
    cols = slice(max(col0, 0), max(col0 + CELLS_PER_SIDE, 0))
    return field[rows, cols]


def aggregate(
    field: np.ndarray, origin: tuple[float, float], tiles: Sequence[Tile], how: str = "sum"
) -> np.ndarray:
    """Sum or mean of a 100 m field inside each tile. `origin` is the field's top-left corner."""
    values = np.zeros(len(tiles), dtype="float64")
    for index, tile in enumerate(tiles):
        block = _block(field, origin, tile)
        if block.size == 0:
            continue
        values[index] = float(block.sum()) if how == "sum" else float(block.mean())
    return values


def _mean_where_built(
    height: np.ndarray, origin: tuple[float, float], tiles: Sequence[Tile]
) -> np.ndarray:
    """Mean height over the cells that have any height, so empty cells do not dilute it."""
    total = aggregate(height, origin, tiles, how="sum")
    count = aggregate((height > 0).astype("float32"), origin, tiles, how="sum")
    return np.divide(total, count, out=np.zeros_like(total), where=count > 0)


def attributes(
    tiles: Sequence[Tile],
    population: np.ndarray,
    built: np.ndarray,
    height: np.ndarray,
    origin: tuple[float, float],
) -> list[dict]:
    """One record per tile: people, density, built fraction, mean height, and both bounds."""
    people = aggregate(population, origin, tiles, how="sum")
    built_m2 = aggregate(built, origin, tiles, how="sum")
    heights = _mean_where_built(height, origin, tiles)
    rows: list[dict] = []
    for index, tile in enumerate(tiles):
        lat, lon = tile.centre_wgs84
        rows.append(
            {
                "id": tile.id,
                "x_km": tile.x_km,
                "y_km": tile.y_km,
                "population": round(float(people[index]), 1),
                "density_per_km2": round(float(people[index]), 1),
                "built_fraction": round(float(built_m2[index]) / (KM * KM), 4),
                "mean_height_m": round(float(heights[index]), 2),
                "bounds_mollweide": list(tile.bounds),
                "bounds_wgs84": [round(v, 6) for v in tile.bounds_wgs84],
                "centre": [round(lat, 6), round(lon, 6)],
            }
        )
    return rows


def select_densest(rows: Iterable[dict], count: int) -> list[dict]:
    return sorted(rows, key=lambda row: -float(row.get("density_per_km2", 0.0)))[:count]


def select_stratified(rows: Iterable[dict], count: int) -> list[dict]:
    """The densest tile of each built-fraction tercile in turn, highest tercile first."""
    by_built = sorted(rows, key=lambda row: -float(row.get("built_fraction", 0.0)))
    if not by_built:
        return []
    terciles = [list(part) for part in np.array_split(np.array(by_built, dtype=object), TERCILES)]
    queues = [
        sorted(part, key=lambda row: -float(row.get("density_per_km2", 0.0))) for part in terciles
    ]
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


def select_random(rows: Iterable[dict], count: int, *, seed: int) -> list[dict]:
    """A seeded draw among the tiles where anyone lives."""
    populated = [row for row in rows if float(row.get("population", 0.0)) > 0]
    rng = np.random.default_rng(seed)
    take = min(count, len(populated))
    picked = rng.choice(len(populated), size=take, replace=False)
    return [populated[int(index)] for index in picked]
