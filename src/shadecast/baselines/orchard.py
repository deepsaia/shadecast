"""Plant trees as crowns, not pixels, and choose the spacing between them.

An earlier planner selected individual raster cells, which conflated one pixel with
one tree. At 1 m resolution a pixel is 1 m2 of canopy, while a real street tree has
a crown roughly 6 m across, about 28 m2. That made a 2.3 million dollar budget look
like 26,000 trees when it is closer to 930, and it made the spacing sweep run from
0 to 2 m when real street-tree spacing is 6 to 12 m. Both ends of that sweep were
denser than anyone plants: spacing 0 m is a solid slab of canopy, which is a park,
not a street-tree programme.

This planner fixes the unit. A tree is a disk. The budget buys a number of trees.
The only decision is how far apart to put them, swept across the range a city
actually chooses within, where 6 m means crowns just touching into a closed canopy
and 30 m means widely spaced specimens.
"""

from __future__ import annotations

import logging

import numpy as np

from ..interventions import CATALOGUE, feasibility_mask
from .greedy import rank_surface

logger = logging.getLogger(__name__)

# A mature small-to-medium urban street tree: crown about 6 m across.
CROWN_RADIUS_M = 3.0


def crown_area_m2(radius_m: float = CROWN_RADIUS_M) -> float:
    return float(np.pi * radius_m**2)


def cost_per_tree(
    kind: str = "tree", radius_m: float = CROWN_RADIUS_M, years: int = 20, discount: float = 0.03
) -> float:
    """All-in cost of one tree: canopy area times unit cost, plus maintenance."""
    spec = CATALOGUE[kind]
    capital = crown_area_m2(radius_m) * spec.unit_cost
    annual = capital * spec.maintenance_frac
    return capital + sum(annual / (1 + discount) ** year for year in range(1, years + 1))


def _disk(radius_px: int) -> tuple[np.ndarray, np.ndarray]:
    span = np.arange(-radius_px, radius_px + 1)
    rows, cols = np.meshgrid(span, span, indexing="ij")
    inside = (rows**2 + cols**2) <= radius_px**2
    return rows[inside], cols[inside]


def select(
    budget_usd: float,
    tmrt: np.ndarray,
    *,
    weights: np.ndarray,
    umep_lc: np.ndarray,
    building_h: np.ndarray,
    spacing_m: float,
    crown_radius_m: float = CROWN_RADIUS_M,
    res_m: float = 1.0,
    threshold: float = 45.0,
    kind: str = "tree",
    surface: np.ndarray | None = None,
) -> tuple[np.ndarray, float, int]:
    """Place as many trees as the budget allows, at least `spacing_m` apart.

    Returns (canopy mask, spent, number of trees actually planted).
    """
    feasible = feasibility_mask(umep_lc, building_h, kind)
    # `surface` lets a caller rank on something other than area harm, which is how the
    # network objective plants along corridors instead of across the hottest ground.
    ranking = rank_surface(tmrt, weights, threshold) if surface is None else surface
    harm = ranking * feasible
    canopy = np.zeros(harm.shape, dtype=bool)
    if harm.max() <= 0:
        return canopy, 0.0, 0

    unit = cost_per_tree(kind, crown_radius_m)
    wanted = int(budget_usd // unit)
    if wanted <= 0:
        return canopy, 0.0, 0

    crown_px = max(1, round(crown_radius_m / res_m))
    space_px = max(crown_px, round(spacing_m / res_m))

    blocked = ~feasible
    rows, cols = np.nonzero(harm > 0)
    rows, cols = rows[np.argsort(-harm[rows, cols])], cols[np.argsort(-harm[rows, cols])]

    crown_r, crown_c = _disk(crown_px)
    block_r, block_c = _disk(space_px)
    height, width = harm.shape
    planted = 0

    for row, col in zip(rows, cols, strict=True):
        if blocked[row, col]:
            continue
        cr = np.clip(row + crown_r, 0, height - 1)
        cc = np.clip(col + crown_c, 0, width - 1)
        canopy[cr, cc] = True
        br = np.clip(row + block_r, 0, height - 1)
        bc = np.clip(col + block_c, 0, width - 1)
        blocked[br, bc] = True
        planted += 1
        if planted >= wanted:
            break

    if planted < wanted:
        logger.info(
            "spacing %.0f m fits only %d of %d trees the budget allows (%.0f%%)",
            spacing_m,
            planted,
            wanted,
            100 * planted / wanted,
        )
    return canopy, planted * unit, planted
