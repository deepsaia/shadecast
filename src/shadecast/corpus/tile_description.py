"""Describe every 1 km tile of an urban centre from the rasters that share its grid.

An urban centre is an exact set of 1 km GHS grid cells, so listing its tiles is a computation,
not a choice. Each tile gets its population, density, built fraction and mean height before any
bundle exists.
"""

from __future__ import annotations

import logging

from shapely.geometry.base import BaseGeometry

from . import ucdb
from .tile_rasters import TileRasters
from .tiling import attributes, tiles_of
from .urban_centre import UrbanCentre

logger = logging.getLogger(__name__)


def boundary(centre: UrbanCentre) -> BaseGeometry:
    """The urban centre polygon in World Mollweide, an exact union of 1 km cells."""
    polygons = ucdb.polygons()
    match = polygons.loc[polygons[ucdb.ID] == centre.id, "geometry"]
    if match.empty:
        raise KeyError(f"no boundary for urban centre {centre.id}")
    return match.iloc[0]


def describe(centre: UrbanCentre) -> list[dict]:
    """Every tile of the centre with population, density, built fraction and height."""
    polygon = boundary(centre)
    tiles = tiles_of(polygon)
    rows = attributes(tiles, TileRasters.read(polygon.bounds))
    logger.info("%s: %d tiles described", centre.slug, len(tiles))
    return rows
