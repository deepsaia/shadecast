"""Fetch and read GHSL 100 m raster products on the shared Mollweide grid.

GHS-POP, GHS-BUILT-S and GHS-BUILT-H are published the same way: one zip per 1,000 km tile,
anonymously, from the JRC open data host, with the tile named by row and column. One fetcher
serves all three, and one windowed reader returns a 100 m array in the grid's own coordinates
so that per-tile sums over an urban centre need no reprojection at all.

Ocean-only tiles are absent from the listing. For a coastal city that is a normal condition,
logged and skipped, not a failure; a window with no tile at all is.
"""

from __future__ import annotations

import io
import logging
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.windows import from_bounds

from . import ghs_grid

logger = logging.getLogger(__name__)

CACHE_ROOT = Path.home() / ".cache" / "shadecast"
DOWNLOAD_TIMEOUT_S = 600

Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class GhsProduct:
    """One GHSL raster product: where its tiles live and how they are named."""

    key: str  # the cited source key
    stem: str  # file stem up to the tile suffix, such as GHS_POP_E2020_GLOBE_R2023A_54009_100_V1_0
    base_url: str  # the tiles directory on the JRC host
    cache_name: str  # subdirectory of the local cache
    nodata: float | None = None

    def tile_url(self, row: int, col: int) -> str:
        return f"{self.base_url}/{self.stem}_{ghs_grid.tile_name(row, col)}.zip"

    def local_path(self, row: int, col: int, cache_root: Path = CACHE_ROOT) -> Path:
        return (
            Path(cache_root) / self.cache_name / f"{self.stem}_{ghs_grid.tile_name(row, col)}.tif"
        )


def local_tile(product: GhsProduct, row: int, col: int, cache_root: Path = CACHE_ROOT) -> Path:
    """The cached GeoTIFF for one tile, fetched and unpacked on first use."""
    target = product.local_path(row, col, cache_root)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    url = product.tile_url(row, col)
    logger.info("fetching %s", url)
    response = requests.get(url, timeout=DOWNLOAD_TIMEOUT_S)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        inner = next(name for name in archive.namelist() if name.endswith(".tif"))
        target.write_bytes(archive.read(inner))
    return target


def snap_outward(bounds: Bounds, step: float = ghs_grid.CELL_M) -> Bounds:
    """Expand a Mollweide box to whole cells."""
    minx, miny, maxx, maxy = bounds
    return (
        math.floor(minx / step) * step,
        math.floor(miny / step) * step,
        math.ceil(maxx / step) * step,
        math.ceil(maxy / step) * step,
    )


def tiles_for_bounds(bounds: Bounds) -> list[tuple[int, int]]:
    """Every 1,000 km tile a Mollweide box touches."""
    minx, miny, maxx, maxy = bounds
    top_left = ghs_grid.tile_rc(minx, maxy)
    bottom_right = ghs_grid.tile_rc(maxx - 1e-6, miny + 1e-6)
    return [
        (row, col)
        for row in range(top_left[0], bottom_right[0] + 1)
        for col in range(top_left[1], bottom_right[1] + 1)
    ]


def _place(
    out: np.ndarray, origin: tuple[float, float], source: Path, bounds: Bounds, nodata: float | None
) -> int:
    """Read the part of one tile inside the bounds into the output array. Returns cells read."""
    with rasterio.open(source) as src:
        tile_bounds = src.bounds
        minx = max(bounds[0], tile_bounds.left)
        miny = max(bounds[1], tile_bounds.bottom)
        maxx = min(bounds[2], tile_bounds.right)
        maxy = min(bounds[3], tile_bounds.top)
        if minx >= maxx or miny >= maxy:
            return 0
        window = from_bounds(minx, miny, maxx, maxy, transform=src.transform)
        data = src.read(1, window=window).astype("float32")
        fill = src.nodata if nodata is None else nodata
    if fill is not None:
        data[data == fill] = 0.0
    data[data < 0] = 0.0
    row0 = round((origin[1] - maxy) / ghs_grid.CELL_M)
    col0 = round((minx - origin[0]) / ghs_grid.CELL_M)
    out[row0 : row0 + data.shape[0], col0 : col0 + data.shape[1]] = data
    return int(data.size)


def read_window(
    product: GhsProduct, bounds: Bounds, cache_root: Path = CACHE_ROOT
) -> tuple[np.ndarray, tuple[float, float]]:
    """A 100 m array covering the bounds, and the (x, y) of its top-left corner.

    Missing values and the product's nodata read as zero, which is the right meaning for
    population, built surface and height alike.
    """
    snapped = snap_outward(bounds)
    minx, miny, maxx, maxy = snapped
    shape = (
        round((maxy - miny) / ghs_grid.CELL_M),
        round((maxx - minx) / ghs_grid.CELL_M),
    )
    out = np.zeros(shape, dtype="float32")
    origin = (minx, maxy)
    read = 0
    for row, col in tiles_for_bounds(snapped):
        try:
            source = local_tile(product, row, col, cache_root)
        except (requests.HTTPError, zipfile.BadZipFile, StopIteration) as exc:
            logger.debug(
                "%s tile %s unavailable: %s", product.key, ghs_grid.tile_name(row, col), exc
            )
            continue
        read += _place(out, origin, source, snapped, product.nodata)
    if read == 0:
        raise RuntimeError(f"no {product.key} tile covers the window {snapped}")
    return out, origin
