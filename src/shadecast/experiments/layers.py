"""Load the rasters every experiment scores against, once and identically.

Experiments that load their own layers drift apart, and a drifted baseline is the
quietest way to make two results incomparable. Everything an experiment needs about a
city comes from here, so a factorial cell and a targeting cell are scored on the same
ground.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio

from ..data.landcover import to_umep
from ..exposure import outdoor_mask, outdoor_weights
from ..repair import building_height

logger = logging.getLogger(__name__)


def _read(bundle: Path, name: str) -> np.ndarray:
    with rasterio.open(Path(bundle) / name) as src:
        return src.read(1)


def city_layers(bundle: Path, surrogate_dir: Path) -> dict:
    """Every raster an experiment needs, plus the baseline daylight-mean Tmrt field."""
    heights = building_height(bundle)
    population = _read(bundle, "population.tif")
    with rasterio.open(Path(bundle) / "Trees.tif") as src:
        profile = src.profile
    return {
        "heights": heights,
        "canopy": _read(bundle, "Trees.tif"),
        "population": population,
        "umep": to_umep(_read(bundle, "landcover.tif"), heights),
        "outdoor": outdoor_mask(heights),
        "weights": outdoor_weights(population, heights),
        "baseline": np.load(Path(surrogate_dir) / "baseline" / "tmrt_daylight.npy"),
        "profile": profile,
    }
