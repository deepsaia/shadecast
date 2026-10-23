"""Move what was built before tiles into the tile layout, planning first and moving on request.

A bundle built by the old single-tile builder belongs to exactly one tile: the cell its AOI
centre falls in. Moving it there, with its physics, is a rename, so nothing is re-run and no
grid shifts. The plan is computed and shown before anything moves, a held generation lock
refuses the whole migration, and an existing target is never overwritten.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from .legacy_city import LegacyCity
from .migration import Migration
from .move import Move
from .tile import Tile
from .tile_paths import TilePaths

logger = logging.getLogger(__name__)

LOCK_NAME = ".generating.lock"


def tile_of_bundle(bundle: Path) -> Tile:
    """The tile a legacy bundle belongs to, from the AOI centre its provenance records."""
    provenance = json.loads((Path(bundle) / "provenance.json").read_text())
    aoi = provenance.get("aoi", {})
    return Tile.at_wgs84(float(aoi.get("lat")), float(aoi.get("lon")))


def plan(legacy: LegacyCity, paths: TilePaths) -> Migration:
    """The moves that take a legacy city into its tile, bundle first."""
    moves = [Move(Path(legacy.bundle), paths.bundle, "bundle")]
    if Path(legacy.surrogate).exists():
        moves.append(Move(Path(legacy.surrogate), paths.surrogate, "surrogate"))
    return Migration(paths, tuple(moves))


def held_locks(migrations: list[Migration]) -> list[Path]:
    """Generation locks under any directory about to move."""
    return [
        move.source / LOCK_NAME
        for migration in migrations
        for move in migration
        if (move.source / LOCK_NAME).exists()
    ]


def _check(migration: Migration) -> None:
    locks = held_locks([migration])
    if locks:
        raise RuntimeError(
            f"a generator holds {locks[0]}; run the migration again when it has finished"
        )
    for move in migration:
        if move.target.exists():
            raise FileExistsError(f"{move.target} exists; refusing to overwrite the {move.label}")


def _record_tile(migration: Migration) -> None:
    """Write the tile into the moved bundle's provenance, so the bundle knows where it is."""
    path = migration.paths.bundle / "provenance.json"
    provenance = json.loads(path.read_text())
    tile = migration.paths.tile
    lat, lon = tile.centre_wgs84
    provenance["tile"] = {
        "id": tile.id,
        "urban_centre": migration.paths.urban_centre,
        "bounds_mollweide": list(tile.bounds),
        "bounds_wgs84": [round(value, 6) for value in tile.bounds_wgs84],
        "centre": [round(lat, 6), round(lon, 6)],
    }
    path.write_text(json.dumps(provenance, indent=2))


def apply(migration: Migration) -> None:
    """Perform the moves, then record the tile in the bundle's provenance."""
    _check(migration)
    for move in migration:
        move.target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(move.source), str(move.target))
        logger.info("moved %s to %s", move.source, move.target)
    _record_tile(migration)
