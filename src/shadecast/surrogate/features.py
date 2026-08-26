"""Assemble the model input stack for one city.

Seven channels, each chosen because the measured physics says it matters:

    placement        what is being added, the thing we vary
    baseline Tmrt    how hot the pixel already is, which sets the headroom
    building height  what already casts shade and blocks sky
    canopy height    existing shade, so the model learns saturation
    sky openness     the local view of sky, which sets how much a new tree can block
    is_water         water behaves unlike any other surface thermally
    is_vegetated     ground that already evapotranspires

Sky openness is derived from building and canopy geometry rather than read from the
engine, so a bundle can be featurised without having run the physics first. That
matters because the surrogate is meant to replace engine calls, not require them.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

# Normalisation constants. Fixed rather than fitted per city so that a model trained
# on one city sees the same scale in another, which is the point of the transfer track.
IN_CHANNELS_ORDER = (
    "placement",
    "baseline_tmrt",
    "building_height",
    "canopy_height",
    "sky_openness",
    "is_water",
    "is_vegetated",
)

TMRT_SCALE = 80.0
HEIGHT_SCALE = 30.0
CANOPY_SCALE = 30.0
OPENNESS_RADIUS_M = 25.0

WATER_CLASS = 80
VEGETATED_CLASSES = (10, 20, 30, 40, 90, 95, 100)


def sky_openness(
    building_height: np.ndarray,
    canopy_height: np.ndarray,
    res_m: float = 1.0,
    radius_m: float = OPENNESS_RADIUS_M,
) -> np.ndarray:
    """A cheap proxy for sky view factor from local obstruction height.

    The engine computes a true sky view factor by ray casting, which costs about
    130 seconds per square kilometre. This is a smoothed inverse of nearby
    obstruction height, which is far cruder but costs milliseconds and carries the
    signal the model actually needs: how enclosed a pixel already is.
    """
    obstruction = np.maximum(building_height, canopy_height).astype("float32")
    local = ndimage.uniform_filter(obstruction, size=max(1, int(radius_m / res_m)))
    return np.clip(1.0 - local / HEIGHT_SCALE, 0.0, 1.0).astype("float32")


def stack(
    placement: np.ndarray,
    baseline_tmrt: np.ndarray,
    *,
    building_height: np.ndarray,
    canopy_height: np.ndarray,
    land_cover: np.ndarray,
    res_m: float = 1.0,
) -> np.ndarray:
    """Return the (7, H, W) input stack, all channels roughly unit scaled."""
    return np.stack(
        [
            placement.astype("float32"),
            (baseline_tmrt / TMRT_SCALE).astype("float32"),
            (building_height / HEIGHT_SCALE).astype("float32"),
            (canopy_height / CANOPY_SCALE).astype("float32"),
            sky_openness(building_height, canopy_height, res_m),
            (land_cover == WATER_CLASS).astype("float32"),
            np.isin(land_cover, VEGETATED_CLASSES).astype("float32"),
        ]
    )
