"""Design of experiments over the intervention space.

Physics runs are the hard budget: roughly 160 to 280 seconds per square kilometre.
A naive approach would simulate one realistic plan per training example, which is
ruinously slow. The measured response makes something much better possible.

Cooling from a new tree is steeply local. Measured on two cities, it falls from
about 18 C at the tree to under 0.1 C by 26 m in dense Ahmedabad and 71 m in
treeless Lagos. So interventions placed further apart than that reach produce
**non-overlapping** response fields, and a single simulation yields one independent
observation per intervention rather than one per run.

That is the core idea here. Sparse probe designs harvest hundreds of clean
single-intervention responses from one physics call. Dense designs are then needed
only to learn where superposition breaks down, which is the part a kernel cannot
predict on its own.
"""

from __future__ import annotations

import logging

import numpy as np
from scipy import ndimage
from skimage.morphology import skeletonize

logger = logging.getLogger(__name__)

# Measured effective reach, the distance at which cooling falls below 0.1 C:
# 26 m in dense Ahmedabad, 71 m in treeless Lagos. Probe spacing is set from the
# larger figure. Spacing does not need to eliminate overlap entirely, only to make
# it negligible: at 100 m spacing the midpoint contribution is around 0.1 C against
# a peak of 12 to 18 C, so under 1 percent contamination.
REACH_M = 71.0
PROBE_SPACING_M = 100.0


def sparse_probe(
    feasible: np.ndarray,
    rng: np.random.Generator,
    *,
    spacing_m: float = PROBE_SPACING_M,
    res_m: float = 1.0,
    jitter: float = 0.35,
) -> np.ndarray:
    """Isolated interventions on a jittered lattice, spaced beyond the reach.

    Each placed pixel yields an independent response, so one simulation returns
    many observations. The jitter stops the lattice from aliasing with the street
    grid, which would sample only one geometric context.
    """
    step = max(1, int(spacing_m / res_m))
    rows, cols = feasible.shape
    placement = np.zeros_like(feasible, dtype=bool)
    amplitude = int(step * jitter)

    for row in range(step // 2, rows, step):
        for col in range(step // 2, cols, step):
            r = row + (rng.integers(-amplitude, amplitude + 1) if amplitude else 0)
            c = col + (rng.integers(-amplitude, amplitude + 1) if amplitude else 0)
            r = int(np.clip(r, 0, rows - 1))
            c = int(np.clip(c, 0, cols - 1))
            if feasible[r, c]:
                placement[r, c] = True
                continue
            # Nudge onto the nearest feasible pixel rather than dropping the probe,
            # otherwise the design silently under-samples built-up neighbourhoods.
            window = feasible[
                max(0, r - step // 4) : r + step // 4, max(0, c - step // 4) : c + step // 4
            ]
            if window.any():
                offsets = np.argwhere(window)
                pick = offsets[rng.integers(len(offsets))]
                placement[max(0, r - step // 4) + pick[0], max(0, c - step // 4) + pick[1]] = True
    return placement


def random_uniform(
    feasible: np.ndarray, rng: np.random.Generator, *, coverage: float = 0.05
) -> np.ndarray:
    """Independent pixels at a target coverage of the feasible area."""
    options = np.argwhere(feasible)
    if len(options) == 0:
        return np.zeros_like(feasible, dtype=bool)
    count = min(len(options), int(coverage * feasible.sum()))
    chosen = options[rng.choice(len(options), size=count, replace=False)]
    placement = np.zeros_like(feasible, dtype=bool)
    placement[chosen[:, 0], chosen[:, 1]] = True
    return placement


def clustered(
    feasible: np.ndarray,
    rng: np.random.Generator,
    *,
    coverage: float = 0.05,
    blob_m: float = 20.0,
    res_m: float = 1.0,
) -> np.ndarray:
    """Contiguous patches, which is how planting actually happens.

    Overlapping responses inside a patch are exactly where linear superposition of
    single-tree kernels fails, so these designs carry the interaction signal.
    """
    field = rng.normal(size=feasible.shape)
    smoothed = ndimage.gaussian_filter(field, sigma=blob_m / res_m)
    smoothed[~feasible] = -np.inf
    budget = int(coverage * feasible.sum())
    if budget <= 0:
        return np.zeros_like(feasible, dtype=bool)
    threshold = np.partition(smoothed.ravel(), -budget)[-budget]
    return (smoothed >= threshold) & feasible


def corridor(
    feasible: np.ndarray,
    rng: np.random.Generator,
    *,
    coverage: float = 0.05,
    width_m: float = 3.0,
    res_m: float = 1.0,
) -> np.ndarray:
    """Linear plantings along the open network, the street tree case.

    Approximated by thinning the feasible area to its skeleton and dilating, which
    follows streets and open corridors without needing a separate road layer.
    """
    skeleton = skeletonize(feasible)
    width = max(1, int(width_m / res_m))
    thick = ndimage.binary_dilation(skeleton, iterations=width) & feasible
    options = np.argwhere(thick)
    if len(options) == 0:
        return clustered(feasible, rng, coverage=coverage, res_m=res_m)
    budget = min(len(options), int(coverage * feasible.sum()))
    chosen = options[rng.choice(len(options), size=budget, replace=False)]
    placement = np.zeros_like(feasible, dtype=bool)
    placement[chosen[:, 0], chosen[:, 1]] = True
    return placement


FAMILIES = ("sparse_probe", "random_uniform", "clustered", "corridor")
