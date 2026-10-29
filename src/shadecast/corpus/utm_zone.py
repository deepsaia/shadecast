"""A UTM zone: the conformal, north-up frame every tile and bundle is built in.

The engine casts shadows on a north-up grid with square metres, which UTM gives and Mollweide
does not. A tile therefore belongs to a zone, named as the zone number and hemisphere
(43N, 23S), and all tiles of one urban centre share the zone of its centroid so that they
never overlap at a zone boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from pyproj import CRS
from pyproj import Transformer

WGS84 = "EPSG:4326"
ID_PATTERN = re.compile(r"^(\d{1,2})([NS])$")


@lru_cache(maxsize=256)
def _transformer(source: str, target: str) -> Transformer:
    return Transformer.from_crs(source, target, always_xy=True)


@dataclass(frozen=True)
class UtmZone:
    number: int
    south: bool

    @classmethod
    def from_lonlat(cls, lon: float, lat: float) -> UtmZone:
        number = min(60, max(1, int((lon + 180) // 6) + 1))
        return cls(number, lat < 0)

    @classmethod
    def from_id(cls, text: str) -> UtmZone:
        match = ID_PATTERN.match(text.strip())
        if match is None:
            raise ValueError(f"{text!r} is not a UTM zone id such as 43N")
        return cls(int(match.group(1)), match.group(2) == "S")

    @property
    def id(self) -> str:
        return f"{self.number}{'S' if self.south else 'N'}"

    @property
    def epsg(self) -> int:
        return (32700 if self.south else 32600) + self.number

    @property
    def crs(self) -> CRS:
        return CRS.from_epsg(self.epsg)

    def from_wgs84(self, lon: float, lat: float) -> tuple[float, float]:
        x, y = _transformer(WGS84, f"EPSG:{self.epsg}").transform(lon, lat)
        return float(x), float(y)

    def to_wgs84(self, x: float, y: float) -> tuple[float, float]:
        """Longitude and latitude of a point in this zone."""
        lon, lat = _transformer(f"EPSG:{self.epsg}", WGS84).transform(x, y)
        return float(lon), float(lat)

    def transformer_from(self, source: str) -> Transformer:
        """Project geometry from another coordinate system into this zone."""
        return _transformer(source, f"EPSG:{self.epsg}")

    def transformer_to(self, target: str) -> Transformer:
        return _transformer(f"EPSG:{self.epsg}", target)
