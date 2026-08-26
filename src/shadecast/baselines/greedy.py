"""Greedy marginal-benefit baseline.

The simplest defensible planner: rank every feasible pixel by how much
heat-exposure harm sits on it, then buy from the top until the budget runs out.

It ignores interaction between placements entirely. A tree shades its neighbours,
so the true marginal benefit of the tenth tree on a street depends on the first
nine, and greedy cannot see that. That blindness is deliberate. It is the floor
that search methods have to beat, and if they cannot beat it the benchmark should
say so.
"""

from __future__ import annotations

import numpy as np

from ..interventions import cost, feasibility_mask


def rank_surface(tmrt: np.ndarray, weights: np.ndarray, threshold: float = 45.0) -> np.ndarray:
    """Harm density: excess degrees times the people who experience them."""
    return np.clip(tmrt - threshold, 0, None) * weights


def select(
    kind: str,
    budget_usd: float,
    tmrt: np.ndarray,
    *,
    weights: np.ndarray,
    umep_lc: np.ndarray,
    building_h: np.ndarray,
    res_m: float = 1.0,
    threshold: float = 45.0,
) -> tuple[np.ndarray, float, int]:
    """Choose pixels for one intervention type within budget.

    Returns (placement mask, spent, n_pixels).
    """
    feasible = feasibility_mask(umep_lc, building_h, kind)
    harm = rank_surface(tmrt, weights, threshold) * feasible
    if harm.max() <= 0:
        return np.zeros_like(feasible), 0.0, 0

    # Cost is linear in area, so the budget converts straight to a pixel count.
    unit = cost(kind, np.ones(1, dtype=bool), res_m)
    n = int(budget_usd // unit)
    n = min(n, int(feasible.sum()))
    if n <= 0:
        return np.zeros_like(feasible), 0.0, 0

    flat = harm.ravel()
    idx = np.argpartition(flat, -n)[-n:]
    idx = idx[flat[idx] > 0]

    placement = np.zeros(flat.size, dtype=bool)
    placement[idx] = True
    placement = placement.reshape(harm.shape)
    return placement, cost(kind, placement, res_m), int(placement.sum())
