"""Score the surrogate on what it is actually for.

Pixel error alone is the wrong measure. Three things matter, in this order.

**The tail must survive.** Cooling is about 18 C at a planted pixel and under 0.1 C
beyond 26 m. A model that nails the near field and flattens the tail would look
excellent on mean error while destroying the spillover, which is the effect this
whole benchmark exists to measure. So error is reported per distance band.

**The aggregate must be right.** The benchmark scores plans on population weighted
exposure, which integrates the whole field. A surrogate can be locally noisy and
still be perfectly useful if that integral is unbiased.

**The ranking must be right.** A search only needs to know which of two plans is
better. A surrogate that is biased but monotone is fine for optimisation, and a
surrogate that is unbiased but scrambles the ordering is useless. Rank correlation
over held out designs is therefore the decisive number.
"""

from __future__ import annotations

import logging

import numpy as np
from scipy import ndimage, stats

logger = logging.getLogger(__name__)

DISTANCE_BANDS_M = ((0, 0), (1, 2), (3, 5), (6, 10), (11, 20), (21, 40), (41, 80))


def distance_bands(
    truth: np.ndarray, predicted: np.ndarray, placement: np.ndarray, res_m: float = 1.0
) -> list[dict]:
    """Mean truth, mean prediction and error, banded by distance from an intervention."""
    distance = np.asarray(ndimage.distance_transform_edt(~placement), dtype="float64") * res_m
    rows: list[dict] = []
    for low, high in DISTANCE_BANDS_M:
        mask = (distance >= low) & (distance <= high)
        if mask.sum() < 100:
            continue
        rows.append(
            {
                "band_m": f"{low}-{high}",
                "pixels": int(mask.sum()),
                "truth_C": round(float(truth[mask].mean()), 4),
                "predicted_C": round(float(predicted[mask].mean()), 4),
                "bias_C": round(float((predicted[mask] - truth[mask]).mean()), 4),
                "mae_C": round(float(np.abs(predicted[mask] - truth[mask]).mean()), 4),
            }
        )
    return rows


def aggregate_error(truth: np.ndarray, predicted: np.ndarray, weights: np.ndarray) -> dict:
    """Error in the weighted integral, which is what a plan is actually scored on."""
    total = weights.sum()
    if total <= 0:
        return {"truth_C": 0.0, "predicted_C": 0.0, "relative_error": 0.0}
    truth_mean = float((truth * weights).sum() / total)
    predicted_mean = float((predicted * weights).sum() / total)
    relative = abs(predicted_mean - truth_mean) / max(abs(truth_mean), 1e-9)
    return {
        "truth_C": round(truth_mean, 4),
        "predicted_C": round(predicted_mean, 4),
        "relative_error": round(relative, 4),
    }


def zero_baseline(truth: np.ndarray) -> float:
    """Error of the trivial model that predicts no change anywhere.

    This is the number every reported error must be compared against. The response
    field is mostly near zero, so a surrogate can post an impressive looking mean
    absolute error while being strictly worse than predicting nothing at all. On one
    sparse probe design the field mean is 0.008 C, so an MAE of 0.08 C is ten times
    worse than doing nothing, not ten times better.
    """
    return float(np.abs(truth).mean())


def skill(truth: np.ndarray, predicted: np.ndarray) -> dict:
    """Skill against the predict-nothing baseline. Positive means it earned its keep."""
    baseline = zero_baseline(truth)
    model = float(np.abs(predicted - truth).mean())
    return {
        "mae_C": round(model, 5),
        "zero_baseline_mae_C": round(baseline, 5),
        "skill": round(1.0 - model / max(baseline, 1e-12), 4),
        "beats_predicting_nothing": bool(model < baseline),
    }


def ranking(truth_scores: list[float], predicted_scores: list[float]) -> dict:
    """How well the surrogate orders plans, which is all a search needs."""
    if len(truth_scores) < 3:
        return {"spearman": None, "kendall": None, "n": len(truth_scores)}
    spearman = stats.spearmanr(truth_scores, predicted_scores)
    kendall = stats.kendalltau(truth_scores, predicted_scores)
    return {
        "spearman": round(float(spearman.statistic), 4),
        "kendall": round(float(kendall.statistic), 4),
        "n": len(truth_scores),
    }


def speedup(engine_seconds: float, surrogate_seconds: float) -> dict:
    """How much cheaper one evaluation became."""
    factor = engine_seconds / max(surrogate_seconds, 1e-9)
    return {
        "engine_seconds": round(engine_seconds, 2),
        "surrogate_seconds": round(surrogate_seconds, 5),
        "speedup": round(factor, 1),
        # A 1,000 evaluation search on one city, which is the number that decides
        # whether the benchmark is runnable by anyone else.
        "search_hours_engine": round(engine_seconds * 1000 / 3600, 1),
        "search_hours_surrogate": round(surrogate_seconds * 1000 / 3600, 4),
    }
