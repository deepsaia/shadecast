"""Assemble the model input stack for one plan over one scene.

Eleven channels, each chosen because the measured physics says it matters:

    placement           what is being added, the thing we vary
    baseline Tmrt       how hot the pixel already is, which sets the headroom
    building height     what already casts shade and blocks sky
    canopy height       existing shade, so the model learns saturation
    sky openness        a cheap proxy for the sky view, from local obstruction height
    is_water            water behaves unlike any other surface thermally
    is_vegetated        ground that already evapotranspires
    sky view factor     the engine's own ray-cast sky view, from the baseline run
    sunlit fraction     the share of daylight hours the sun reaches the pixel, same run
    sun noon elevation  how high the sun climbs on the design day, constant over the tile
    sun noon side       whether the noon sun stands south or north, constant over the tile

The first seven are the original set and form the ``base`` channel set. The last four were
added on 2026-10-23 and need the baseline run, which every scene needs anyway for the
baseline Tmrt. Training can use either set, and the manifest records which.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy import ndimage

from .scene import Scene

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
    "sky_view_factor",
    "sunlit_fraction",
    "sun_noon_elevation",
    "sun_noon_side",
)
BASE_CHANNEL_COUNT = 7
CHANNEL_SETS = {
    "base": IN_CHANNELS_ORDER[:BASE_CHANNEL_COUNT],
    "engine": IN_CHANNELS_ORDER,
}

TMRT_SCALE = 80.0
HEIGHT_SCALE = 30.0
CANOPY_SCALE = 30.0
ELEVATION_SCALE = 90.0
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
    signal the model actually needs: how enclosed a pixel already is. It stays in the
    stack beside the engine's value so the two can be compared.
    """
    obstruction = np.maximum(building_height, canopy_height).astype("float32")
    local = ndimage.uniform_filter(obstruction, size=max(1, int(radius_m / res_m)))
    return np.clip(1.0 - local / HEIGHT_SCALE, 0.0, 1.0).astype("float32")


def stack(placement: np.ndarray, scene: Scene, res_m: float = 1.0) -> np.ndarray:
    """Return the (11, H, W) input stack, every channel roughly unit scaled."""
    shape = placement.shape
    return np.stack(
        [
            placement.astype("float32"),
            (scene.baseline_tmrt / TMRT_SCALE).astype("float32"),
            (scene.building_height / HEIGHT_SCALE).astype("float32"),
            (scene.canopy_height / CANOPY_SCALE).astype("float32"),
            sky_openness(scene.building_height, scene.canopy_height, res_m),
            (scene.land_cover == WATER_CLASS).astype("float32"),
            np.isin(scene.land_cover, VEGETATED_CLASSES).astype("float32"),
            scene.sky_view_factor.astype("float32"),
            scene.sunlit_fraction.astype("float32"),
            np.full(shape, scene.sun.elevation_deg / ELEVATION_SCALE, dtype="float32"),
            np.full(shape, scene.sun.side, dtype="float32"),
        ]
    )


def select(features: np.ndarray, names: Sequence[str]) -> np.ndarray:
    """The channels named, in the order given, from a full (11, H, W) stack."""
    return features[[IN_CHANNELS_ORDER.index(name) for name in names]]


def channel_set_for(count: int) -> str:
    """The channel set with this many channels, for a checkpoint that recorded only a count."""
    for key, names in CHANNEL_SETS.items():
        if len(names) == count:
            return key
    raise ValueError(f"no channel set has {count} channels; sets are {sorted(CHANNEL_SETS)}")
