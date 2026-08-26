"""Study-area definition and the common raster grid every layer is aligned to."""

from __future__ import annotations

import math
from dataclasses import dataclass

from affine import Affine
from pyproj import CRS, Transformer
from rasterio.transform import from_origin


@dataclass(frozen=True)
class AOI:
    """A square study area defined by a centre point and a side length in metres.

    Every layer in a city bundle is resampled onto this exact grid, so that
    SOLWEIG's requirement that all surface models share extent and pixel size
    is satisfied by construction rather than by hope.
    """

    name: str
    lat: float
    lon: float
    side_m: int = 1000
    res_m: float = 1.0

    @property
    def utm_epsg(self) -> int:
        zone = int((self.lon + 180) // 6) + 1
        return (32600 if self.lat >= 0 else 32700) + zone

    @property
    def crs(self) -> CRS:
        return CRS.from_epsg(self.utm_epsg)

    @property
    def centre_utm(self) -> tuple[float, float]:
        tf = Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)
        return tf.transform(self.lon, self.lat)

    @property
    def bounds_utm(self) -> tuple[float, float, float, float]:
        """(minx, miny, maxx, maxy) snapped so the grid origin is a whole pixel."""
        cx, cy = self.centre_utm
        half = self.side_m / 2
        minx = math.floor((cx - half) / self.res_m) * self.res_m
        miny = math.floor((cy - half) / self.res_m) * self.res_m
        return minx, miny, minx + self.side_m, miny + self.side_m

    @property
    def bounds_wgs84(self) -> tuple[float, float, float, float]:
        minx, miny, maxx, maxy = self.bounds_utm
        tf = Transformer.from_crs(self.crs, "EPSG:4326", always_xy=True)
        corners = ((minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy))
        xs, ys = zip(*[tf.transform(x, y) for x, y in corners], strict=True)
        return min(xs), min(ys), max(xs), max(ys)

    @property
    def shape(self) -> tuple[int, int]:
        n = round(self.side_m / self.res_m)
        return n, n

    @property
    def transform(self) -> Affine:
        minx, _, _, maxy = self.bounds_utm
        return from_origin(minx, maxy, self.res_m, self.res_m)

    def at_res(self, res_m: float) -> AOI:
        return AOI(self.name, self.lat, self.lon, self.side_m, res_m)


# Phase 0 target. Ahmedabad ran the first Heat Action Plan in South Asia (2013),
# which makes it the natural plan-rediscovery validation case.
CITIES: dict[str, AOI] = {
    "ahmedabad": AOI("ahmedabad", 23.0225, 72.5850, side_m=1000, res_m=1.0),
}
