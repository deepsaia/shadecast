"""The study area a tile is built on: the tile itself, as an AOI the builder understands."""

from __future__ import annotations

from ..aoi import AOI
from .tile import KM
from .tile import Tile

# Half a metre keeps the snapped grid origin on the tile's kilometre line after the centre
# has been round-tripped through latitude and longitude.
NUDGE_M = 0.5


def aoi_for_tile(tile: Tile, res_m: float = 1.0) -> AOI:
    """A 1 km AOI whose bounds are exactly the tile's."""
    centre_x, centre_y = tile.centre_utm
    lon, lat = tile.zone.to_wgs84(centre_x + NUDGE_M, centre_y + NUDGE_M)
    aoi = AOI(tile.id, lat, lon, side_m=int(KM), res_m=res_m, epsg=tile.zone.epsg)
    if tuple(aoi.bounds_utm) != tuple(float(value) for value in tile.bounds):
        raise ValueError(f"AOI for {tile.id} does not land on the tile: {aoi.bounds_utm}")
    return aoi
