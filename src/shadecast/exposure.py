"""Turn "where people live" into "whose outdoor exposure this pixel represents".

SOLWEIG is a pedestrian-level model. Its Tmrt over a building footprint is not
a temperature anyone experiences, so scoring it there is meaningless. But the
dasymetric population step deliberately places everyone *inside* buildings.
Naively multiplying the two scores the one mask where the physics does not apply.

The fix is to move population out onto the outdoor pixels people actually use.
Each resident is spread over nearby outdoor ground with a distance decay, which
encodes the ordinary fact that you experience the street outside your home, the
route to transit, and the shade you can reach, not your own roof.

This is the outdoor-exposure channel. Indoor heat, which drives most mortality
among the over-65s, is a separate problem this benchmark does not claim to solve.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter


def outdoor_weights(
    pop: np.ndarray, building_h: np.ndarray, reach_m: float = 25.0, res_m: float = 1.0
) -> np.ndarray:
    """Redistribute residents onto outdoor pixels within walking reach.

    reach_m is the decay scale, roughly "the outdoor space right by home".
    """
    outdoor = building_h <= 0
    if not outdoor.any():
        raise ValueError("No outdoor pixels in AOI")

    sigma = reach_m / res_m
    spread = gaussian_filter(pop.astype("float64"), sigma=sigma, mode="nearest")
    spread *= outdoor  # keep only what landed outdoors

    # Renormalise so the AOI's population total is conserved after masking.
    total = float(pop.sum())
    s = spread.sum()
    if s > 0:
        spread *= total / s
    return spread.astype("float32")


def outdoor_mask(building_h: np.ndarray) -> np.ndarray:
    return building_h <= 0
