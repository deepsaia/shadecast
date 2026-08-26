"""Choose a study area from population density rather than by hand.

Hand-picking a box is neither reproducible nor reliable. A city-centre coordinate
usually lands in a commercial district that is empty at night: seeding on Nairobi's
centre found 1,562 residents, while scanning for the densest window found 154,245.
The first hand-picked Ahmedabad centre sat on the Sabarmati and pulled 21% water.

Scanning GHS-POP is deterministic, defensible, and avoids water automatically
because nobody lives on it.

This lives apart from `aoi` to break a circular import: population extraction needs
an AOI to read against, so the selector cannot sit inside the AOI module itself.
"""

from __future__ import annotations

import logging

import numpy as np
from pyproj import Transformer
from scipy.ndimage import uniform_filter

from .aoi import AOI
from .cities import City
from .data.population import coarse

logger = logging.getLogger(__name__)

SEARCH_KM = 16.0
GHS_POP_RES_M = 100.0


def select(
    city: City, *, search_km: float = SEARCH_KM, side_m: int = 1000, res_m: float = 1.0
) -> AOI:
    """Return the densest populated window of `side_m` near the city seed."""
    scan = AOI(city.key, city.lat, city.lon, side_m=int(search_km * 1000), res_m=GHS_POP_RES_M)
    population = coarse(scan)

    window = max(1, int(side_m / GHS_POP_RES_M))
    density = uniform_filter(population.astype("float64"), size=window, mode="constant")

    # Keep whole windows inside the scan extent so no edge window is truncated.
    pad = window // 2
    interior = np.full(density.shape, -np.inf)
    rows, cols = density.shape
    interior[pad : rows - pad, pad : cols - pad] = density[pad : rows - pad, pad : cols - pad]

    row, col = np.unravel_index(int(np.argmax(interior)), interior.shape)

    minx, _, _, maxy = scan.bounds_utm
    easting = minx + (col + 0.5) * scan.res_m
    northing = maxy - (row + 0.5) * scan.res_m
    transformer = Transformer.from_crs(scan.crs, "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(easting, northing)

    logger.info(
        "%s: study area at %.4f,%.4f (seed %.4f,%.4f)", city.key, lat, lon, city.lat, city.lon
    )
    return AOI(city.key, lat, lon, side_m=side_m, res_m=res_m)
