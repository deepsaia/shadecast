"""A city's 1 km tiles as a grid for a map: where each cell is, how many live there, which have a model.

Parallel lists rather than one object per cell: a city has thousands of cells and a map wants them
light. A described tile without coordinates, from an older tiles file, is counted but not drawn.
"""

from __future__ import annotations

from pydantic import BaseModel

COLUMNS = ("west", "south", "east", "north", "density_per_km2", "residents", "modelled")
BOUNDS = "bounds_wgs84"


class TileGrid(BaseModel):
    columns: tuple[str, ...] = COLUMNS
    ids: list[str]
    cells: list[list[float]]
    described: int

    @classmethod
    def of(cls, rows: list[dict], modelled: set[str]) -> TileGrid:
        ids: list[str] = []
        cells: list[list[float]] = []
        for row in rows:
            bounds = row.get(BOUNDS)
            if not isinstance(bounds, list) or len(bounds) != 4:
                continue
            tile_id = str(row.get("id"))
            ids.append(tile_id)
            cells.append(_cell(row, bounds, tile_id in modelled))
        return cls(ids=ids, cells=cells, described=len(rows))


def _cell(row: dict, bounds: list, has_model: bool) -> list[float]:
    """Three arguments: the row, its bounds already checked, and the flag the models root answers."""
    return [
        *(round(float(value), 5) for value in bounds),
        round(float(row.get("density_2020_per_km2") or 0.0), 1),
        round(float(row.get("population_2020") or 0.0), 1),
        1.0 if has_model else 0.0,
    ]
