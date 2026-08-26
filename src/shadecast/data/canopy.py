"""Tree canopy height from the Meta / WRI 1 m global Canopy Height Model.

SOLWEIG needs vegetation height above ground (its CDSM input), and canopy shade
is the single largest lever in most heat-adaptation portfolios, so this layer
carries a lot of the eventual signal.

Served as anonymous cloud-optimised GeoTIFFs on AWS Open Data. Tiles are indexed
by a global GeoJSON footprint file which we cache once.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.warp import reproject
from shapely.geometry import box, shape

from ..aoi import AOI

BASE = "https://dataforgood-fb-data.s3.amazonaws.com/forests/v1/alsgedi_global_v6_float"
CACHE = Path.home() / ".cache" / "shadecast"


def _tile_index() -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    local = CACHE / "meta_chm_tiles.geojson"
    if not local.exists():
        r = requests.get(f"{BASE}/tiles.geojson", timeout=300)
        r.raise_for_status()
        local.write_bytes(r.content)
    return json.loads(local.read_text())["features"]


def tiles_for(aoi: AOI) -> list[str]:
    """Quadkeys of every CHM tile intersecting the AOI."""
    want = box(*aoi.bounds_wgs84)
    out = []
    for f in _tile_index():
        if shape(f["geometry"]).intersects(want):
            props = f["properties"]
            out.append(str(props.get("tile") or props.get("quadkey")))
    return out


def canopy_height(aoi: AOI) -> np.ndarray:
    """Vegetation height above ground on the AOI grid, 0 where there is none."""
    keys = tiles_for(aoi)
    if not keys:
        raise RuntimeError(f"No Meta CHM tile covers {aoi.name}")

    out = np.full(aoi.shape, np.nan, dtype="float32")
    for key in keys:
        with rasterio.open(f"{BASE}/chm/{key}.tif") as src:
            buf = np.full(aoi.shape, np.nan, dtype="float32")
            reproject(
                source=rasterio.band(src, 1),
                destination=buf,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=aoi.transform,
                dst_crs=aoi.crs,
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
            out = np.where(np.isnan(out), buf, out)

    out = np.nan_to_num(out, nan=0.0)
    # The CHM encodes "no vegetation" as 0 and saturates around 30 m; negatives
    # are noise from the regression, not real.
    return np.clip(out, 0.0, None).astype("float32")
