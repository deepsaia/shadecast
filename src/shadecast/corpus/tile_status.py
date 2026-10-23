"""How far each tile of an urban centre has come, read from the files that prove it."""

from __future__ import annotations

from pathlib import Path

from .tile_paths import TilePaths
from .urban_centre import UrbanCentre

STAGES = ("bundle", "baseline", "surrogate", "model", "results")


def tile_status(centre: UrbanCentre, tiles_root: Path) -> dict:
    """Per-tile stage flags and the k of N totals for one urban centre."""
    rows = [
        {"tile": paths.tile.id, **paths.stages()}
        for paths in TilePaths.existing(tiles_root, centre.id)
    ]
    totals = {stage: sum(1 for row in rows if row.get(stage)) for stage in STAGES}
    return {"urban_centre": centre.id, "tiles": centre.tiles, "totals": totals, "rows": rows}


def summary_line(status: dict) -> str:
    """One line a reader can scan: how many tiles have reached each stage."""
    tiles = int(status.get("tiles", 0))
    totals = status.get("totals", {})
    return ", ".join(f"{totals.get(stage, 0)} of {tiles} {stage}" for stage in STAGES)
