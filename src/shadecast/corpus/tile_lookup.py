"""Find a city's built tiles from its name, so nobody has to know an urban centre id.

A corpus key such as ``savannah`` is answered from the selection file without loading the
urban centre database, and a bare number is taken as the centre id. Anything else is a
slug or a name resolved through the database. Only tiles with a bundle count as built.
"""

from __future__ import annotations

import json
from pathlib import Path

from .. import cities
from .tile_paths import TilePaths
from .tile_selection import TileSelection
from .tiling import select_densest
from .tiling import select_stratified
from .urban_centres import UrbanCentres

ALL = "all"


def centre_id(text: str) -> int:
    """The urban centre an id, a corpus key, a slug or a name refers to."""
    query = str(text).strip()
    if query.isdigit():
        return int(query)
    keyed = {str(entry.get("key")): int(str(entry.get("ucdb_id", 0))) for entry in cities.selection()}
    if query in keyed:
        return keyed[query]
    return UrbanCentres.load().resolve(query).id


def built_tiles(text: str, tiles_root: Path) -> list[TilePaths]:
    """Every tile of the centre that has a bundle, in tile id order."""
    found = TilePaths.existing(tiles_root, centre_id(text))
    return [paths for paths in found if paths.stages().bundle]


def one_built_tile(text: str, tile: str | None, tiles_root: Path) -> TilePaths:
    """The one built tile a command means; names the choices when there are several."""
    found = built_tiles(text, tiles_root)
    ids = ", ".join(paths.tile.id for paths in found) or "none"
    if tile is not None:
        for paths in found:
            if paths.tile.id == tile:
                return paths
        raise ValueError(f"{text} has no built tile {tile}; built tiles: {ids}")
    if not found:
        raise ValueError(f"{text} has no built tile yet; run 'sdc build {text}' first")
    if len(found) > 1:
        raise ValueError(f"{text} has {len(found)} built tiles ({ids}); add --tile <id>")
    return found[0]


def densest_built_tile(text: str, tiles_root: Path) -> TilePaths:
    """The built tile with most residents, by the centre's tiles file; the only one when one."""
    found = built_tiles(text, tiles_root)
    if not found:
        raise ValueError(f"{text} has no built tile yet; run 'sdc build {text}' first")
    return _densest_of(text, found, "--tiles")


def _ranked_ids(tiles_json: Path) -> list[str]:
    """Tile ids densest first, from the centre's tiles file, or none when it is absent."""
    if not tiles_json.exists():
        return []
    rows = json.loads(tiles_json.read_text()).get("tiles", [])
    rows = sorted(rows, key=lambda row: float(row.get("population_2020") or 0), reverse=True)
    return [str(row.get("id")) for row in rows]


def simulated_tiles(
    text: str, tiles: str | None, tiles_root: Path, selection: TileSelection | None = None
) -> list[TilePaths]:
    """Tiles of the city with simulated physics: all by default, named ones, or a K selection.

    A city plans across every kind of area, so its model learns from every tile that has
    physics, which is exactly what simulate produced. Names narrow that set, and a named tile
    without physics is refused rather than silently dropped. A selection picks the K densest,
    or K spread over built-fraction terciles, among the tiles with physics, ranked by the
    centre's tiles file.
    """
    with_physics = [paths for paths in TilePaths.existing(tiles_root, centre_id(text)) if paths.stages().physics]
    if not with_physics:
        raise ValueError(f"{text} has no simulated physics yet; run 'sdc simulate treeshade {text}' first")
    if selection is not None and selection.wants():
        return _selected(text, with_physics, selection)
    if tiles is None or tiles.strip().lower() in ("", ALL):
        return with_physics
    chosen = []
    for tile_id in [part.strip() for part in tiles.split(",") if part.strip()]:
        match = [paths for paths in with_physics if paths.tile.id == tile_id]
        if not match:
            have = ", ".join(paths.tile.id for paths in with_physics)
            raise ValueError(f"{text} tile {tile_id} has no simulated physics; tiles with physics: {have}")
        chosen.extend(match)
    return chosen


def _densest_of(text: str, found: list[TilePaths], option: str) -> TilePaths:
    """The tile with most residents among ``found``, by the centre's tiles file."""
    if len(found) == 1:
        return found[0]
    for tile_id in _ranked_ids(found[0].tiles_json):
        for paths in found:
            if paths.tile.id == tile_id:
                return paths
    ids = ", ".join(paths.tile.id for paths in found)
    raise ValueError(f"{text} has {len(found)} tiles ({ids}) and no tiles.json to rank them; add {option}")


def densest_simulated_tile(text: str, tiles_root: Path) -> TilePaths:
    """The tile with physics and most residents, to assess a city's model against."""
    return _densest_of(text, simulated_tiles(text, None, tiles_root), "--tile")


def _selected(text: str, found: list[TilePaths], selection: TileSelection) -> list[TilePaths]:
    """The K densest or K stratified tiles among ``found``, using the centre's tiles file."""
    tiles_json = found[0].tiles_json
    if not tiles_json.exists():
        raise ValueError(f"{text} has no tiles.json to rank tiles; run 'sdc tile list {text}' first")
    by_id = {paths.tile.id: paths for paths in found}
    rows = [row for row in json.loads(tiles_json.read_text()).get("tiles", []) if row.get("id") in by_id]
    if selection.densest:
        picked = select_densest(rows, selection.densest)
    else:
        picked = select_stratified(rows, selection.stratified or 0)
    return [by_id[str(row.get("id"))] for row in picked]
