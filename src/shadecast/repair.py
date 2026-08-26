"""Backfill layers that a bundle predates.

Bundles built by an older version of the builder can be missing layers that were
added later. Rebuilding is not always an option: once physics has been run against
a bundle's geometry, every generated response is tied to that exact grid, and a
rebuild that shifts the study area silently invalidates hours of simulation.

So missing layers are recomputed onto the bundle's own recorded grid instead.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import rasterio

from .aoi import AOI
from .data import population as population_layer
from .data.landcover import to_umep

logger = logging.getLogger(__name__)


def aoi_from_provenance(bundle: Path) -> AOI:
    """Reconstruct the exact grid a bundle was built on."""
    record = json.loads((Path(bundle) / "provenance.json").read_text())["aoi"]
    return AOI(
        record["name"], record["lat"], record["lon"], side_m=record["side_m"], res_m=record["res_m"]
    )


def _write_like(bundle: Path, name: str, array: np.ndarray, dtype: str) -> Path:
    """Write a layer using an existing layer's georeferencing, so grids cannot drift."""
    with rasterio.open(Path(bundle) / "DEM.tif") as reference:
        profile = reference.profile
    profile.update(dtype=dtype, count=1, compress="deflate", tiled=True)
    target = Path(bundle) / name
    with rasterio.open(target, "w", **profile) as destination:
        destination.write(array.astype(dtype), 1)
    return target


def building_height(bundle: Path) -> np.ndarray:
    with rasterio.open(Path(bundle) / "Building_DSM.tif") as src:
        surface = src.read(1)
    with rasterio.open(Path(bundle) / "DEM.tif") as src:
        terrain = src.read(1)
    return np.maximum(surface - terrain, 0)


def backfill(bundle: Path) -> list[str]:
    """Add any missing layers to a bundle. Returns what was written."""
    bundle = Path(bundle)
    written: list[str] = []
    heights = building_height(bundle)

    if not (bundle / "population.tif").exists():
        aoi = aoi_from_provenance(bundle)
        logger.info("%s: backfilling population on its recorded grid", bundle.name)
        _write_like(bundle, "population.tif", population_layer.dasymetric(aoi, heights), "float32")
        written.append("population.tif")

    if not (bundle / "landcover_umep.tif").exists() and (bundle / "landcover.tif").exists():
        with rasterio.open(bundle / "landcover.tif") as src:
            cover = src.read(1)
        _write_like(bundle, "landcover_umep.tif", to_umep(cover, heights), "uint8")
        written.append("landcover_umep.tif")

    return written
