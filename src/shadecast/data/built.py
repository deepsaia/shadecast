"""Built-up surface and building height from GHS-BUILT, on the GHS grid.

GHS-BUILT-S gives the built-up surface in square metres inside every 100 m cell, so a 1 km
tile's built fraction is its sum over one million square metres. GHS-BUILT-H gives the average
net building height per cell. Both share the GHS-POP grid, so per-tile attributes come straight
from windowed reads with no reprojection. They are used to describe tiles before any is built,
which is what lets a selection be stratified by morphology rather than by density alone.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .ghs_product import CACHE_ROOT, Bounds, GhsProduct, read_window

SURFACE_SOURCE = "ghs_built_s"  # keys in cited_sources.json
HEIGHT_SOURCE = "ghs_built_h"

JRC = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL"

GHS_BUILT_S = GhsProduct(
    key=SURFACE_SOURCE,
    stem="GHS_BUILT_S_E2020_GLOBE_R2023A_54009_100_V1_0",
    base_url=f"{JRC}/GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E2020_GLOBE_R2023A_54009_100/V1-0/tiles",
    cache_name="ghsbuilt",
    nodata=65535.0,
)
GHS_BUILT_H = GhsProduct(
    key=HEIGHT_SOURCE,
    stem="GHS_BUILT_H_ANBH_E2018_GLOBE_R2023A_54009_100_V1_0",
    base_url=f"{JRC}/GHS_BUILT_H_GLOBE_R2023A/GHS_BUILT_H_ANBH_E2018_GLOBE_R2023A_54009_100/V1-0/tiles",
    cache_name="ghsbuilt",
    nodata=255.0,
)


def built_surface(
    bounds: Bounds, cache_root: Path = CACHE_ROOT
) -> tuple[np.ndarray, tuple[float, float]]:
    """Built-up square metres per 100 m cell over the bounds, and the array's top-left corner."""
    return read_window(GHS_BUILT_S, bounds, cache_root)


def building_height(
    bounds: Bounds, cache_root: Path = CACHE_ROOT
) -> tuple[np.ndarray, tuple[float, float]]:
    """Average net building height in metres per 100 m cell over the bounds."""
    return read_window(GHS_BUILT_H, bounds, cache_root)
