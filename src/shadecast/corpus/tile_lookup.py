"""Find a city's built tiles from its name, so nobody has to know an urban centre id.

A corpus key such as ``savannah`` is answered from the selection file without loading the
urban centre database, and a bare number is taken as the centre id. Anything else is a
slug or a name resolved through the database. Only tiles with a bundle count as built.
"""

from __future__ import annotations

from pathlib import Path

from .. import cities
from .tile_paths import TilePaths
from .urban_centres import UrbanCentres


def centre_id(text: str) -> int:
    """The urban centre an id, a corpus key, a slug or a name refers to."""
    query = str(text).strip()
    if query.isdigit():
        return int(query)
    keyed = {
        str(entry.get("key")): int(str(entry.get("ucdb_id", 0))) for entry in cities.selection()
    }
    if query in keyed:
        return keyed[query]
    return UrbanCentres.load().resolve(query).id


def built_tiles(text: str, tiles_root: Path) -> list[TilePaths]:
    """Every tile of the centre that has a bundle, in tile id order."""
    found = TilePaths.existing(tiles_root, centre_id(text))
    return [paths for paths in found if paths.stages().get("bundle")]


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
