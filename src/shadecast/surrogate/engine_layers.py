"""Layers the engine computed for the baseline run, which the surrogate can read for free.

A baseline run leaves two rasters behind that describe the untouched geometry better than
any proxy: the sky view factor it ray-cast for every pixel, and an hourly stack of which
pixels the sun reaches. Each is read once and cached beside the daylight mean, so the
92 MB shadow stack is not re-read for every patch set.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from ..pipeline import DAYLIGHT_BANDS

SVF_FILE = Path("processed_inputs") / "SVF" / "SkyViewFactor_0_0.tif"
SHADOW_FILE = Path("output_folder") / "0_0" / "Shadow_0_0.tif"
SVF_CACHE = "svf.npy"
SUNLIT_CACHE = "sunlit_daylight.npy"


def sky_view_factor(baseline_dir: Path) -> np.ndarray:
    """The engine's sky view factor, 0 for an enclosed pixel to 1 for open sky."""
    cache = Path(baseline_dir) / SVF_CACHE
    if cache.exists():
        return np.load(cache)
    source = Path(baseline_dir) / SVF_FILE
    if not source.exists():
        raise FileNotFoundError(f"the baseline run kept no sky view factor at {source}")
    with rasterio.open(source) as raster:
        svf = raster.read(1).astype("float32")
    np.save(cache, svf)
    return svf


def sunlit_fraction(baseline_dir: Path) -> np.ndarray:
    """Share of the daylight hours in which the sun reaches each pixel.

    The engine writes 1 for a sunlit pixel and 0 for a shaded one, with fractions under
    vegetation. Checked against noon Tmrt in Ahmedabad: 70.5 C where 1, 48.8 C where 0.
    """
    cache = Path(baseline_dir) / SUNLIT_CACHE
    if cache.exists():
        return np.load(cache)
    source = Path(baseline_dir) / SHADOW_FILE
    if not source.exists():
        raise FileNotFoundError(f"the baseline run kept no shadow stack at {source}")
    with rasterio.open(source) as raster:
        bands = [band for band in DAYLIGHT_BANDS if band < raster.count]
        sunlit = np.mean([raster.read(band + 1) for band in bands], axis=0).astype("float32")
    np.save(cache, sunlit)
    return sunlit
