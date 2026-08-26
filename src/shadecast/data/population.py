"""Population exposure, downscaled to the simulation grid.

GHS-POP R2023A (100 m, Mollweide) is the source. It is chosen over WorldPop for
one practical reason: WorldPop's server refuses HTTP range requests, so a
windowed read is impossible and you must pull an entire country file. GHS-POP is
tiled at 1,000,000 m and serves ranges, so one modest tile covers a city.

100 m population on a 1 m thermal grid would be misleading if spread uniformly,
since it would place people in the middle of roads. Each coarse cell's count is
redistributed across the building volume inside it (footprint area times height),
a standard dasymetric step that is only possible because GlobalBuildingAtlas
gives us complete heights.
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

import numpy as np
import rasterio
import requests
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.warp import reproject

from ..aoi import AOI

logger = logging.getLogger(__name__)

BASE = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/"
    "GHS_POP_E2020_GLOBE_R2023A_54009_100/V1-0/tiles"
)
STEM = "GHS_POP_E2020_GLOBE_R2023A_54009_100_V1_0"
CACHE = Path.home() / ".cache" / "shadecast" / "ghspop"

# GHSL Mollweide tiling: 1,000,000 m tiles from the top-left of the world extent.
X0, Y0, TILE = -18041000.0, 9020048.0, 1_000_000.0


def tile_rc(lat: float, lon: float) -> tuple[int, int]:
    x, y = Transformer.from_crs("EPSG:4326", "ESRI:54009", always_xy=True).transform(lon, lat)
    return int((Y0 - y) // TILE) + 1, int((x - X0) // TILE) + 1


def _local_tile(row: int, col: int) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    tif = CACHE / f"{STEM}_R{row}_C{col}.tif"
    if tif.exists():
        return tif
    r = requests.get(f"{BASE}/{STEM}_R{row}_C{col}.zip", timeout=600)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        inner = next(n for n in z.namelist() if n.endswith(".tif"))
        tif.write_bytes(z.read(inner))
    return tif


def tiles_for(aoi: AOI) -> list[tuple[int, int]]:
    """Every GHS-POP tile intersecting the AOI corners."""
    minx, miny, maxx, maxy = aoi.bounds_wgs84
    corners = [(miny, minx), (miny, maxx), (maxy, minx), (maxy, maxx)]
    return sorted({tile_rc(la, lo) for la, lo in corners})


def coarse(aoi: AOI) -> np.ndarray:
    """GHS-POP counts resampled onto the AOI grid, still 100 m in character."""
    out = np.full(aoi.shape, np.nan, dtype="float32")
    for row, col in tiles_for(aoi):
        try:
            tif = _local_tile(row, col)
        except (requests.HTTPError, zipfile.BadZipFile, StopIteration) as exc:
            # Ocean-only tiles are absent from the JRC listing, which is normal
            # for coastal cities rather than a failure.
            logger.debug("GHS-POP tile R%d_C%d unavailable: %s", row, col, exc)
            continue
        with rasterio.open(tif) as src:
            buf = np.full(aoi.shape, np.nan, dtype="float32")
            reproject(
                source=rasterio.band(src, 1),
                destination=buf,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=aoi.transform,
                dst_crs=aoi.crs,
                dst_nodata=np.nan,
                # Counts, not density. Nearest replicates the parent cell value
                # into its children; we divide by the child count below so the
                # population total is conserved.
                resampling=Resampling.nearest,
            )
            out = np.where(np.isnan(out), buf, out)
    pop = np.nan_to_num(out, nan=0.0)
    pop[pop < 0] = 0.0
    return (pop / ((100.0 / aoi.res_m) ** 2)).astype("float32")


def dasymetric(aoi: AOI, building_height: np.ndarray, block_m: int = 100) -> np.ndarray:
    """Population per pixel, concentrated into buildings by volume share."""
    c = coarse(aoi)
    vol = building_height.astype("float64")
    out = np.zeros(aoi.shape, dtype="float32")
    step = int(block_m / aoi.res_m)
    for r0 in range(0, aoi.shape[0], step):
        for c0 in range(0, aoi.shape[1], step):
            sl = (slice(r0, r0 + step), slice(c0, c0 + step))
            total = float(c[sl].sum())
            if total <= 0:
                continue
            v = vol[sl]
            vs = v.sum()
            # No mapped buildings: keep the people rather than discard them.
            out[sl] = (v / vs * total).astype("float32") if vs > 0 else total / v.size
    return out
