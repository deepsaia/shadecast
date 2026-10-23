"""The GHS Mollweide grid shared by GHS-POP, GHS-BUILT and the urban centre boundaries.

Every GHSL raster product sits on one World Mollweide grid of 100 m cells, cut into 1,000 km
tiles named R<row>_C<col> from the top-left of the world extent at (-18,041,000, 9,000,000) m.
The urban centre boundaries in GHS-UCDB are unions of the 1 km cells of the same grid, which is
what lets a tile be a 1 km cell and a tile's population be an exact sum of 100 GHS-POP cells.

The origin is a measured fact, not a convention: the top of row 1 is 9,000,000 m, checked
against the transforms of the cached GHS-POP rasters. An earlier reader used 9,020,048 m and
placed any point in the 20 km band below a row boundary in the wrong tile.
"""

from __future__ import annotations

from pyproj import Transformer

from .ghs_types import TileRC

CRS = "ESRI:54009"
X0 = -18_041_000.0
Y0 = 9_000_000.0
TILE_M = 1_000_000.0
CELL_M = 100.0

TO_MOLLWEIDE = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
TO_WGS84 = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)


def to_mollweide(lon: float, lat: float) -> tuple[float, float]:
    x, y = TO_MOLLWEIDE.transform(lon, lat)
    return float(x), float(y)


def to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Longitude and latitude of a Mollweide point."""
    lon, lat = TO_WGS84.transform(x, y)
    return float(lon), float(lat)


def tile_rc(x: float, y: float) -> TileRC:
    """Row and column of the 1,000 km tile holding a Mollweide point."""
    return int((Y0 - y) // TILE_M) + 1, int((x - X0) // TILE_M) + 1


def tile_name(rc: TileRC) -> str:
    row, col = rc
    return f"R{row}_C{col}"
