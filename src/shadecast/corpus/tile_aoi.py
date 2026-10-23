"""The study area a tile is built on, and the mask of the tile inside it.

The engine casts shadows on a north-up conformal grid, and the Mollweide grid the tiles come
from is neither conformal nor north-up away from its central meridian. So a tile is built on
the UTM square that covers its cell's footprint, and scored only on the pixels inside the cell.
The square is larger than the cell by a ratio that grows with longitude; the ratio is recorded
in provenance because it is also the engine cost.
"""

from __future__ import annotations

import math

import numpy as np
from pyproj import CRS, Transformer
from rasterio.features import rasterize
from shapely.geometry import Polygon
from shapely.ops import transform as transform_geometry

from ..aoi import AOI
from ..data import ghs_grid
from .tile import Tile


def footprint_utm(tile: Tile, crs: CRS) -> Polygon:
    """The cell boundary projected to the given UTM system."""
    to_utm = Transformer.from_crs(ghs_grid.CRS, crs, always_xy=True)
    return transform_geometry(to_utm.transform, tile.polygon)


def aoi_for_tile(tile: Tile, res_m: float = 1.0) -> AOI:
    """The smallest whole-metre UTM square, centred on the cell, that covers the whole cell."""
    lat, lon = tile.centre_wgs84
    probe = AOI(tile.id, lat, lon, side_m=1000, res_m=res_m)
    minx, miny, maxx, maxy = footprint_utm(tile, probe.crs).bounds
    centre_x, centre_y = probe.centre_utm
    half = max(maxx - centre_x, centre_x - minx, maxy - centre_y, centre_y - miny)
    # One extra metre keeps the footprint strictly inside after the grid origin is snapped.
    side = math.ceil(2 * half) + 2
    return AOI(tile.id, lat, lon, side_m=side, res_m=res_m)


def cell_mask(tile: Tile, aoi: AOI) -> np.ndarray:
    """1 where a pixel centre lies inside the cell, 0 elsewhere, on the AOI grid."""
    footprint = footprint_utm(tile, aoi.crs)
    return rasterize(
        [(footprint, 1)], out_shape=aoi.shape, transform=aoi.transform, fill=0, dtype="uint8"
    )
