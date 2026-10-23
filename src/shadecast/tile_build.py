"""Build one tile: a bundle on the square that covers its cell, plus the mask of the cell.

The bundle itself is built exactly as before, by `build.build_city`, so every layer and every
provenance field stays the same. What a tile adds is the choice of study area, the cell mask
that scoring must go through, and a provenance block saying which tile this is and how much
larger than the cell the built square had to be.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import rasterio

from .aoi import AOI
from .build import build_city
from .cities import City
from .corpus.tile import Tile
from .corpus.tile_aoi import aoi_for_tile, cell_mask
from .corpus.tile_paths import TilePaths

logger = logging.getLogger(__name__)

MASK_FILE = "cell_mask.tif"


def _write_mask(bundle: Path, mask: np.ndarray) -> Path:
    with rasterio.open(bundle / "DEM.tif") as reference:
        profile = reference.profile
    profile.update(dtype="uint8", count=1, compress="deflate", tiled=True, nodata=None)
    target = bundle / MASK_FILE
    with rasterio.open(target, "w", **profile) as destination:
        destination.write(mask, 1)
    return target


def tile_record(tile: Tile, aoi: AOI, mask: np.ndarray) -> dict:
    """What provenance says about the tile: which cell, how much square, how much of it counts."""
    lat, lon = tile.centre_wgs84
    cell_area_m2 = float(mask.sum()) * aoi.res_m * aoi.res_m
    return {
        "id": tile.id,
        "bounds_mollweide": list(tile.bounds),
        "bounds_wgs84": [round(value, 6) for value in tile.bounds_wgs84],
        "centre": [round(lat, 6), round(lon, 6)],
        "square_side_m": aoi.side_m,
        "square_over_cell": round(aoi.side_m * aoi.side_m / cell_area_m2, 3),
        "cell_mask": MASK_FILE,
    }


def build_tile(city: City, tile: Tile, paths: TilePaths) -> dict:
    """Build a city's bundle for one tile into the tile layout.

    Three arguments because a tile build is a city, a cell, and where the layout puts them.
    """
    aoi = aoi_for_tile(tile)
    provenance = build_city(city, paths.bundle, aoi=aoi)
    mask = cell_mask(tile, aoi)
    _write_mask(paths.bundle, mask)
    provenance["tile"] = {**tile_record(tile, aoi, mask), "urban_centre": city.ucdb_id}
    provenance["aoi"]["selection"] = f"tile {tile.id} of urban centre {city.ucdb_id}"
    (paths.bundle / "provenance.json").write_text(json.dumps(provenance, indent=2))
    logger.info(
        "%s %s: built on a %d m square, %.2f times the cell",
        city.key,
        tile.id,
        aoi.side_m,
        provenance["tile"]["square_over_cell"],
    )
    return provenance
