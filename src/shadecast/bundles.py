"""Read what a built bundle records: its grid and its building heights."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import rasterio

from .aoi import AOI

logger = logging.getLogger(__name__)


def aoi_from_provenance(bundle: Path) -> AOI:
    """Reconstruct the exact grid a bundle was built on."""
    provenance = json.loads((Path(bundle) / "provenance.json").read_text())
    record = provenance["aoi"]
    # Older bundles carried the city name inside the aoi block; newer ones keep it
    # in a separate city block. Fall back to the directory name.
    name = record.get("name") or provenance.get("city", {}).get("key") or Path(bundle).name
    return AOI(name, record["lat"], record["lon"], side_m=record["side_m"], res_m=record["res_m"])


def building_height(bundle: Path) -> np.ndarray:
    with rasterio.open(Path(bundle) / "Building_DSM.tif") as src:
        surface = src.read(1)
    with rasterio.open(Path(bundle) / "DEM.tif") as src:
        terrain = src.read(1)
    return np.maximum(surface - terrain, 0)
