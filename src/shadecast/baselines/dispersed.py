"""Greedy with a minimum spacing between trees.

Greedy plants wherever the harm is highest. Hot ground is contiguous, so it fills
in solid patches, and trees inside a patch shade ground that neighbouring trees
already shade. Measured across three cities, that wastes a factor of 3.5 to 5 of
the cooling a scattered plan of the same cost delivers.

This planner keeps greedy's targeting and adds one parameter: a minimum distance
between chosen trees. **Spacing zero is exactly greedy**, so the family contains
greedy as a special case and can only match or beat it once the spacing is tuned.
That also makes the result interpretable: the optimal spacing is a number a planting
department can act on, unlike "run this optimiser".

Selection walks the score field in descending order and accepts a pixel only if no
already-accepted tree lies within the spacing radius. That is a score-weighted
Poisson-disk sample, and it costs one disk stamp per accepted tree rather than a
scan of the field per tree.
"""

from __future__ import annotations

import logging

import numpy as np

from ..interventions import cost, feasibility_mask
from .greedy import rank_surface

logger = logging.getLogger(__name__)


def _disk_offsets(radius_px: int) -> tuple[np.ndarray, np.ndarray]:
    """Row and column offsets covering a disk, computed once per plan."""
    span = np.arange(-radius_px, radius_px + 1)
    rows, cols = np.meshgrid(span, span, indexing="ij")
    inside = (rows**2 + cols**2) <= radius_px**2
    return rows[inside], cols[inside]


def select(
    kind: str,
    budget_usd: float,
    tmrt: np.ndarray,
    *,
    weights: np.ndarray,
    umep_lc: np.ndarray,
    building_h: np.ndarray,
    spacing_m: float = 0.0,
    res_m: float = 1.0,
    threshold: float = 45.0,
) -> tuple[np.ndarray, float, int]:
    """Choose tree sites within budget, keeping them at least `spacing_m` apart.

    Returns (placement mask, spent, number of trees).
    """
    feasible = feasibility_mask(umep_lc, building_h, kind)
    harm = rank_surface(tmrt, weights, threshold) * feasible
    if harm.max() <= 0:
        return np.zeros_like(feasible), 0.0, 0

    unit = cost(kind, np.ones(1, dtype=bool), res_m)
    wanted = min(int(budget_usd // unit), int(feasible.sum().item()))
    if wanted <= 0:
        return np.zeros_like(feasible), 0.0, 0

    radius_px = round(spacing_m / res_m)
    placement = np.zeros(harm.shape, dtype=bool)

    if radius_px <= 0:
        # Spacing zero is plain greedy: take the highest-harm pixels outright.
        flat = harm.ravel()
        idx = np.argpartition(flat, -wanted)[-wanted:]
        idx = idx[flat[idx] > 0]
        placement.ravel()[idx] = True
        return placement, cost(kind, placement, res_m), int(placement.sum())

    blocked = ~feasible
    rows, cols = np.nonzero(harm > 0)
    order = np.argsort(-harm[rows, cols])
    rows, cols = rows[order], cols[order]

    disk_r, disk_c = _disk_offsets(radius_px)
    height, width = harm.shape
    taken = 0

    for row, col in zip(rows, cols, strict=True):
        if blocked[row, col]:
            continue
        placement[row, col] = True
        taken += 1
        rr = np.clip(row + disk_r, 0, height - 1)
        cc = np.clip(col + disk_c, 0, width - 1)
        blocked[rr, cc] = True
        if taken >= wanted:
            break

    if taken < wanted:
        # Spacing is binding: the budget cannot be spent at this dispersion. Report
        # honestly rather than silently spending less than asked.
        logger.info(
            "spacing %.1f m limits the plan to %d of %d trees (%.0f%% of budget)",
            spacing_m,
            taken,
            wanted,
            100 * taken / wanted,
        )
    return placement, cost(kind, placement, res_m), taken
