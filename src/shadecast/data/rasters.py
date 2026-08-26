"""Terrain and land cover, pulled unsigned from AWS Open Data.

Originally these came through Microsoft Planetary Computer's STAC. That was
dropped: PC issues short-lived SAS tokens per container, and on 2026-08-26 the
token endpoint began returning 404 for both `elevationeuwest/copernicus` and
`esaworldcover/esaworldcover` while continuing to serve Landsat. A benchmark
cannot depend on a token broker that can partially fail.

AWS Open Data serves the identical products as plain unsigned HTTP with range
requests, so tiles are addressed directly by name and read as windowed COGs.
Fewer moving parts, and genuinely no credentials rather than anonymous-but-brokered.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError
from rasterio.warp import reproject

from ..aoi import AOI

logger = logging.getLogger(__name__)

COP_DEM = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
    "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif"
)
WORLDCOVER = (
    "https://esa-worldcover.s3.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_{ns}{lat:02d}{ew}{lon:03d}_Map.tif"
)


def _corners(aoi: AOI, step: int) -> list[tuple[int, int]]:
    """South-west corners of every `step`-degree tile intersecting the AOI."""
    minx, miny, maxx, maxy = aoi.bounds_wgs84
    lons = sorted({int(math.floor(v / step) * step) for v in (minx, maxx)})
    lats = sorted({int(math.floor(v / step) * step) for v in (miny, maxy)})
    return [(la, lo) for la in lats for lo in lons]


def _url(template: str, lat: int, lon: int) -> str:
    return template.format(
        ns="N" if lat >= 0 else "S", lat=abs(lat), ew="E" if lon >= 0 else "W", lon=abs(lon)
    )


def _mosaic(
    urls: list[str], aoi: AOI, resampling: Resampling, dtype: str, fill: float
) -> np.ndarray:
    out = np.full(aoi.shape, np.nan, dtype="float32")
    hit = 0
    for u in urls:
        try:
            with rasterio.open(f"/vsicurl/{u}") as src:
                buf = np.full(aoi.shape, np.nan, dtype="float32")
                reproject(
                    source=rasterio.band(src, 1),
                    destination=buf,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=aoi.transform,
                    dst_crs=aoi.crs,
                    dst_nodata=np.nan,
                    resampling=resampling,
                )
                out = np.where(np.isnan(out), buf, out)
                hit += 1
        except RasterioIOError as exc:
            # Ocean-only tiles are simply absent from these buckets, which is a
            # normal condition for coastal cities rather than a failure.
            logger.debug("source tile unavailable: %s", exc)
            continue
    if hit == 0:
        raise RuntimeError(f"no source tiles resolved for {aoi.name}")
    return np.nan_to_num(out, nan=fill).astype(dtype)


def terrain(aoi: AOI) -> np.ndarray:
    """Copernicus DEM GLO-30 ground elevation, metres above sea level. 1 degree tiles."""
    urls = [_url(COP_DEM, la, lo) for la, lo in _corners(aoi, 1)]
    # 30 m source onto a fine grid: bilinear, since terrain is smooth.
    return _mosaic(urls, aoi, Resampling.bilinear, "float32", 0.0)


def worldcover(aoi: AOI) -> np.ndarray:
    """ESA WorldCover 10 m land cover classes. 3 degree tiles."""
    urls = [_url(WORLDCOVER, la, lo) for la, lo in _corners(aoi, 3)]
    # Categorical: nearest only, never interpolate a class code.
    return _mosaic(urls, aoi, Resampling.nearest, "uint8", 0)
