"""A tile is one square kilometre of the UTM kilometre grid, inside an urban centre.

Tiles are square on the ground everywhere, north-up, and exactly the grid the engine runs on,
so a tile's bundle is the tile with no mask and no buffer. The id names the zone and the
kilometre corner: ``t43N_249_2546`` is zone 43 north, easting 249 km, northing 2,546 km. All
tiles of an urban centre share the zone of its centroid, so a city on a zone boundary still
gets one non-overlapping grid.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from shapely.geometry import Polygon
from shapely.geometry import box
from shapely.ops import transform as transform_geometry

from .utm_zone import UtmZone

KM = 1000.0
ID_PATTERN = re.compile(r"^t(\d{1,2}[NS])_(-?\d+)_(-?\d+)$")


@dataclass(frozen=True)
class Tile:
    zone: UtmZone
    e_km: int
    n_km: int

    @property
    def id(self) -> str:
        return f"t{self.zone.id}_{self.e_km}_{self.n_km}"

    @classmethod
    def from_id(cls, text: str) -> Tile:
        match = ID_PATTERN.match(text.strip())
        if match is None:
            raise ValueError(f"{text!r} is not a tile id of the form t<zone>_<e_km>_<n_km>")
        return cls(UtmZone.from_id(match.group(1)), int(match.group(2)), int(match.group(3)))

    @classmethod
    def containing(cls, zone: UtmZone, x: float, y: float) -> Tile:
        """The tile holding a point given in the zone's metres.

        Three arguments because a point in UTM is a zone and two coordinates.
        """
        return cls(zone, math.floor(x / KM), math.floor(y / KM))

    @classmethod
    def at_wgs84(cls, lat: float, lon: float) -> Tile:
        zone = UtmZone.from_lonlat(lon, lat)
        return cls.containing(zone, *zone.from_wgs84(lon, lat))

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        minx = int(self.e_km * KM)
        miny = int(self.n_km * KM)
        return minx, miny, minx + int(KM), miny + int(KM)

    @property
    def polygon(self) -> Polygon:
        return box(*self.bounds)

    def polygon_in(self, crs: str) -> Polygon:
        """The tile's footprint in another coordinate system, such as the GHS Mollweide grid."""
        return transform_geometry(self.zone.transformer_to(crs).transform, self.polygon)

    @property
    def centre_utm(self) -> tuple[float, float]:
        minx, miny, _, _ = self.bounds
        return minx + KM / 2, miny + KM / 2

    @property
    def centre_wgs84(self) -> tuple[float, float]:
        """Latitude and longitude of the tile centre."""
        lon, lat = self.zone.to_wgs84(*self.centre_utm)
        return lat, lon

    @property
    def bounds_wgs84(self) -> tuple[float, float, float, float]:
        minx, miny, maxx, maxy = self.bounds
        corners = [self.zone.to_wgs84(x, y) for x in (minx, maxx) for y in (miny, maxy)]
        lons = [corner[0] for corner in corners]
        lats = [corner[1] for corner in corners]
        return min(lons), min(lats), max(lons), max(lats)
