"""The action space: what a planner can actually change, and what it costs.

Every intervention is expressed as an edit to the three rasters SOLWEIG consumes,
which keeps the environment honest. There is no reduced-form cooling coefficient
anywhere; if an intervention cools a pixel it is because the radiation budget says so.

    trees              -> canopy model (CDSM)
    shade structures   -> canopy model, as a flat awning
    de-paving          -> ground cover class on sealed pixels, to grass
    permeable paving   -> ground cover class on sealed pixels, to cobble
    cool roofs         -> ground cover class on roof pixels
    reflective paving  -> ground cover class on sealed pixels

Arms are best grouped by the physical channel they act through, because the channel
decides how far the result can be trusted:

    geometry / shading      trees, shade structures        validated
    surface temperature     de-paving, permeable paving    trusted, longwave only
    shortwave albedo        cool roofs, reflective paving  quarantined, see below
    directional reflectance retro-reflective materials     not representable

The albedo arms are quarantined. Raising ground albedo makes this engine report
cooling, while field measurement over 58 km of treated street in Phoenix reports a
significant rise in pedestrian mean radiant temperature on the road
(Nature Communications 14, 1467, 2023). Retro-reflective materials are the physically
correct version of that arm and cannot be represented at all, because SOLWEIG assumes
Lambertian reflection and building albedo is a single module scalar in the engine.

Costs are per unit and deliberately kept as an editable table rather than buried
in code, because they are the most locally variable numbers in the whole system.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .data.landcover import ASPHALT, COBBLE, GRASS, ROOF, SOIL

# Extensions to the stock UMEP class table, installed into the engine by
# sim.surfaces. Code 3 is deliberately skipped: solweig.py hardcodes `lc_grid == 3`
# as water in two places for the nocturnal water temperature, so reusing it would
# silently make cool roofs behave like ponds.
COOL_ROOF = 4  # high-albedo roof coating
COOL_PAVING = 8  # reflective / light-coloured paving

EXTENDED_ALBEDO = {COOL_ROOF: 0.65, COOL_PAVING: 0.40}


@dataclass(frozen=True)
class InterventionSpec:
    name: str
    unit_cost: float  # USD per pixel-unit (1 m2 at 1 m resolution)
    maintenance_frac: float  # annual maintenance as a fraction of capital
    plantable_on: tuple[int, ...] = ()


# Order-of-magnitude defaults. These are placeholders pending a proper cost
# review and MUST be treated as a tunable input, not a finding.
CATALOGUE = {
    "tree": InterventionSpec(
        "tree", unit_cost=40.0, maintenance_frac=0.08, plantable_on=(GRASS, SOIL, COBBLE, ASPHALT)
    ),
    "cool_roof": InterventionSpec(
        "cool_roof", unit_cost=12.0, maintenance_frac=0.05, plantable_on=(ROOF,)
    ),
    "cool_paving": InterventionSpec(
        "cool_paving", unit_cost=25.0, maintenance_frac=0.04, plantable_on=(ASPHALT, COBBLE)
    ),
    "shade": InterventionSpec(
        "shade", unit_cost=250.0, maintenance_frac=0.03, plantable_on=(ASPHALT, COBBLE, GRASS, SOIL)
    ),
    # Lifting sealed surface and establishing vegetation. This acts through the
    # surface temperature channel, since the UMEP table gives asphalt Ts_deg 0.58
    # and unmanaged grass 0.21, so the ground simply emits less longwave. It does
    # not bounce shortwave onto anyone, which is why it stays usable while the
    # albedo arms are quarantined. The residual albedo change is small and adverse
    # (0.18 -> 0.16), so measured cooling here is a lower bound.
    "depave": InterventionSpec(
        "depave", unit_cost=60.0, maintenance_frac=0.12, plantable_on=(ASPHALT,)
    ),
    # Sealed surface replaced by lighter, rougher paving (Ts_deg 0.58 -> 0.37).
    # Carried mainly as the midpoint of the same channel: if the channel behaves,
    # its cooling must land between asphalt and grass. That ordering is a cheap
    # internal check on the channel itself, not a headline result.
    "permeable": InterventionSpec(
        "permeable", unit_cost=90.0, maintenance_frac=0.04, plantable_on=(ASPHALT,)
    ),
}


def feasibility_mask(umep_lc: np.ndarray, building_h: np.ndarray, kind: str) -> np.ndarray:
    """Where this intervention may physically be placed."""
    spec = CATALOGUE[kind]
    mask = np.isin(umep_lc, spec.plantable_on)
    if kind in ("tree", "shade", "cool_paving", "depave", "permeable"):
        mask &= building_h <= 0  # nothing goes on top of a building
    return mask


def apply(
    kind: str,
    placement: np.ndarray,
    cdsm: np.ndarray,
    umep_lc: np.ndarray,
    *,
    tree_height: float = 8.0,
    shade_height: float = 3.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply an intervention, returning updated (cdsm, land cover).

    `placement` is a boolean raster of chosen pixels.
    Mature tree height is used here; the multi-period track replaces this with a
    growth curve, which is what makes sequencing non-trivial.
    """
    cdsm, umep_lc = cdsm.copy(), umep_lc.copy()
    if kind == "tree":
        cdsm[placement] = np.maximum(cdsm[placement], tree_height)
    elif kind == "shade":
        cdsm[placement] = np.maximum(cdsm[placement], shade_height)
    elif kind == "cool_roof":
        umep_lc[placement] = COOL_ROOF
    elif kind == "cool_paving":
        umep_lc[placement] = COOL_PAVING
    elif kind == "depave":
        umep_lc[placement] = GRASS
    elif kind == "permeable":
        umep_lc[placement] = COBBLE
    else:
        raise KeyError(kind)
    return cdsm, umep_lc


def cost(
    kind: str, placement: np.ndarray, res_m: float, *, years: int = 20, discount: float = 0.03
) -> float:
    """Capital plus discounted maintenance over the planning horizon."""
    spec = CATALOGUE[kind]
    area = float(placement.sum()) * res_m * res_m
    capital = area * spec.unit_cost
    annual = capital * spec.maintenance_frac
    npv_maint = sum(annual / (1 + discount) ** y for y in range(1, years + 1))
    return capital + npv_maint
