"""Build one tile: the bundle on the tile's own square kilometre, into the tile layout.

The bundle is built exactly as before, by `build.build_city`, so every layer and provenance
field stays the same. What a tile adds is the study area, which is the tile itself, and a
provenance block saying which tile and zone the bundle is.
"""

from __future__ import annotations

import json
import logging

from .build import build_city
from .cities import City
from .corpus.tile import Tile
from .corpus.tile_aoi import aoi_for_tile
from .corpus.tile_paths import TilePaths

logger = logging.getLogger(__name__)


def tile_record(tile: Tile) -> dict:
    lat, lon = tile.centre_wgs84
    return {
        "id": tile.id,
        "zone": tile.zone.id,
        "epsg": tile.zone.epsg,
        "bounds_utm": list(tile.bounds),
        "bounds_wgs84": [round(value, 6) for value in tile.bounds_wgs84],
        "centre": [round(lat, 6), round(lon, 6)],
    }


def build_tile(city: City, tile: Tile, paths: TilePaths) -> dict:
    """Build a city's bundle for one tile into the tile layout.

    Three arguments because a tile build is a city, a square, and where the layout puts them.
    """
    provenance = build_city(city, paths.bundle, aoi=aoi_for_tile(tile))
    provenance["tile"] = {**tile_record(tile), "urban_centre": city.ucdb_id}
    provenance["aoi"]["selection"] = f"tile {tile.id} of urban centre {city.ucdb_id}"
    (paths.bundle / "provenance.json").write_text(json.dumps(provenance, indent=2))
    logger.info("%s %s: built", city.key, tile.id)
    return provenance
