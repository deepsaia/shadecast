"""Map ESA WorldCover classes onto the UMEP surface classes SOLWEIG expects.

UMEP ships seven ground classes, each carrying an albedo, emissivity and a
surface-temperature response curve:

    0 cobble stone   1 dark asphalt   2 roofs   5 grass   6 bare soil
    7 water         99 walls

Trees are NOT a ground class. SOLWEIG takes vegetation from the canopy model
(CDSM) instead, so tree-covered ground is mapped to whatever lies beneath it.

Building footprints override WorldCover, because a 3 m building raster localises
roofs far better than a 10 m "built-up" class does.
"""
from __future__ import annotations

import numpy as np

COBBLE, ASPHALT, ROOF, GRASS, SOIL, WATER = 0, 1, 2, 5, 6, 7

# ESA WorldCover -> UMEP ground class
WORLDCOVER_TO_UMEP: dict[int, int] = {
    10: GRASS,    # tree cover: ground beneath, canopy comes from the CDSM
    20: GRASS,    # shrubland
    30: GRASS,    # grassland
    40: GRASS,    # cropland
    50: ASPHALT,  # built-up: sealed surface by default
    60: SOIL,     # bare / sparse vegetation
    70: SOIL,     # snow and ice
    80: WATER,
    90: WATER,    # herbaceous wetland
    95: GRASS,    # mangroves
    100: GRASS,   # moss and lichen
}

# Albedo values used for intervention classes. UMEP's stock table has no cool
# surfaces, so CoolBench extends it; see interventions.py.
ALBEDO = {COBBLE: 0.20, ASPHALT: 0.18, ROOF: 0.18, GRASS: 0.16, SOIL: 0.25, WATER: 0.05}


def to_umep(worldcover: np.ndarray, building_height: np.ndarray) -> np.ndarray:
    """Return a UMEP-coded ground cover raster."""
    out = np.full(worldcover.shape, ASPHALT, dtype="uint8")
    for src, dst in WORLDCOVER_TO_UMEP.items():
        out[worldcover == src] = dst
    # Buildings win over everything, including water misclassification.
    out[building_height > 0] = ROOF
    return out


def summarise(umep: np.ndarray) -> dict[str, float]:
    names = {COBBLE: "cobble", ASPHALT: "asphalt", ROOF: "roof",
             GRASS: "grass", SOIL: "soil", WATER: "water"}
    u, c = np.unique(umep, return_counts=True)
    return {names.get(int(k), str(k)): round(float(v) / umep.size, 4) for k, v in zip(u, c)}
