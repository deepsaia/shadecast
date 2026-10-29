"""Fetch and read GHSL 100 m raster products on the shared Mollweide grid.

GHS-POP, GHS-BUILT-S and GHS-BUILT-H are published the same way: one zip per 1,000 km tile,
anonymously, from the JRC open data host, with the tile named by row and column. One fetcher
serves all three, and one windowed reader returns the cells over a box in the grid's own
coordinates so that per-tile sums over an urban centre need no reprojection at all.

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

import requests

from . import ghs_grid
from .ghs_types import Bounds
from .ghs_types import TileRC
from .raster_window import RasterWindow

logger = logging.getLogger(__name__)

CACHE_ROOT = Path.home() / ".cache" / "shadecast"
DOWNLOAD_TIMEOUT_S = 600


@dataclass(frozen=True)
class GhsProduct:
    """One GHSL raster product: where its tiles live and how they are named."""

    key: str  # the cited source key
    stem: str  # file stem up to the tile suffix, such as GHS_POP_E2020_GLOBE_R2023A_54009_100_V1_0
    base_url: str  # the tiles directory on the JRC host
    cache_name: str  # subdirectory of the local cache
    nodata: float | None = None

    def tile_url(self, rc: TileRC) -> str:
        return f"{self.base_url}/{self.stem}_{ghs_grid.tile_name(rc)}.zip"

    def local_path(self, rc: TileRC, cache_root: Path = CACHE_ROOT) -> Path:
        return Path(cache_root) / self.cache_name / f"{self.stem}_{ghs_grid.tile_name(rc)}.tif"


def local_tile(product: GhsProduct, rc: TileRC, cache_root: Path = CACHE_ROOT) -> Path:
    """The cached GeoTIFF for one tile, fetched and unpacked on first use."""
    target = product.local_path(rc, cache_root)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    url = product.tile_url(rc)
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


def tiles_for_bounds(bounds: Bounds) -> list[TileRC]:
    """Every 1,000 km tile a Mollweide box touches."""
    minx, miny, maxx, maxy = bounds
    first_row, first_col = ghs_grid.tile_rc(minx, maxy)
    last_row, last_col = ghs_grid.tile_rc(maxx - 1e-6, miny + 1e-6)
    return [(row, col) for row in range(first_row, last_row + 1) for col in range(first_col, last_col + 1)]


def read_window(product: GhsProduct, bounds: Bounds, cache_root: Path = CACHE_ROOT) -> RasterWindow:
    """The product's cells over a box, snapped outward to whole cells.

    The cache root is a third argument so tests can point reads at a temporary directory.
    Missing values and the product's nodata read as zero, which is the right meaning for
    population, built surface and height alike.
    """
    snapped = snap_outward(bounds)
    window = RasterWindow.zeros(snapped)
    read = 0
    for rc in tiles_for_bounds(snapped):
        try:
            source = local_tile(product, rc, cache_root)
        except (requests.HTTPError, zipfile.BadZipFile, StopIteration) as exc:
            logger.debug("%s tile %s unavailable: %s", product.key, ghs_grid.tile_name(rc), exc)
            continue
        read += window.paste(source, snapped, product.nodata)
    if read == 0:
        raise RuntimeError(f"no {product.key} tile covers the window {snapped}")
    return window
