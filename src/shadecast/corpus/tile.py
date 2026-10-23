"""A tile is one 1 km cell of the GHS Mollweide grid.

The urban centre boundaries are exact unions of these cells, so a tile belongs to exactly one
urban centre and an urban centre of N km2 has exactly N tiles. The id is the cell's lower-left
corner in Mollweide kilometres, `t<x>_<y>`: globally unique, stable across releases, and
derivable from a coordinate with no lookup.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from shapely.geometry import Polygon, box

from ..data import ghs_grid

KM = 1000.0
ID_PATTERN = re.compile(r"^t(-?\d+)_(-?\d+)$")


@dataclass(frozen=True)
class Tile:
    x_km: int
    y_km: int

    @property
    def id(self) -> str:
        return f"t{self.x_km}_{self.y_km}"

    @classmethod
    def from_id(cls, text: str) -> Tile:
        match = ID_PATTERN.match(text.strip())
        if match is None:
            raise ValueError(f"{text!r} is not a tile id of the form t<x>_<y>")
        return cls(int(match.group(1)), int(match.group(2)))

    @classmethod
    def containing(cls, x: float, y: float) -> Tile:
        """The tile holding a Mollweide point."""
        return cls(math.floor(x / KM), math.floor(y / KM))

    @classmethod
    def at_wgs84(cls, lat: float, lon: float) -> Tile:
        x, y = ghs_grid.to_mollweide(lon, lat)
        return cls.containing(x, y)

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        minx = int(self.x_km * KM)
        miny = int(self.y_km * KM)
        return minx, miny, minx + int(KM), miny + int(KM)

    @property
    def polygon(self) -> Polygon:
        return box(*self.bounds)

    @property
    def centre_mollweide(self) -> tuple[float, float]:
        minx, miny, _, _ = self.bounds
        return minx + KM / 2, miny + KM / 2

    @property
    def centre_wgs84(self) -> tuple[float, float]:
        """Latitude and longitude of the cell centre."""
        lon, lat = ghs_grid.to_wgs84(*self.centre_mollweide)
        return lat, lon

    @property
    def bounds_wgs84(self) -> tuple[float, float, float, float]:
        """Longitude and latitude box enclosing the cell."""
        minx, miny, maxx, maxy = self.bounds
        corners = [ghs_grid.to_wgs84(x, y) for x in (minx, maxx) for y in (miny, maxy)]
        lons = [c[0] for c in corners]
        lats = [c[1] for c in corners]
        return min(lons), min(lats), max(lons), max(lats)
