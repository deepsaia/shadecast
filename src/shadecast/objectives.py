"""What a heat adaptation plan is scored on.

Four objectives, all reported. Scalarising them is the decision-maker's business, not the
simulator's, because the weighting between lives, money and fairness is a
political choice and hard-coding one would quietly make that choice for everyone.

The thermal quantity is mean radiant temperature (Tmrt) from SOLWEIG, aggregated
over the design day's daylight hours. Tmrt is what a body actually experiences
in sun and shade, which is why shade interventions show up in it at all, unlike
air temperature which barely moves at street scale.
"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass

import numpy as np

# Tmrt above this is where heat-stress risk rises steeply for outdoor exposure.
# Not a mortality threshold; see the limits note in the proposal.
TMRT_STRESS_C = 45.0


@dataclass
class Score:
    exposure: float  # population-weighted mean Tmrt, degC
    excess: float  # population-weighted degC-hours above the threshold
    people_at_risk: float  # people in pixels over the threshold
    equity_gap: float  # exposure gap, most vs least dense decile, degC
    cost_usd: float

    def as_dict(self) -> dict:
        return {k: round(float(v), 4) for k, v in asdict(self).items()}


def _pop_weighted_mean(field: np.ndarray, pop: np.ndarray) -> float:
    w = pop.sum()
    return float((field * pop).sum() / w) if w > 0 else float(field.mean())


def equity_gap(field: np.ndarray, pop: np.ndarray, deciles: int = 10) -> float:
    """Exposure difference between the most and least densely populated deciles.

    Population density is a weak proxy for deprivation. It is used here because
    it is globally available; a city with a real deprivation surface should
    substitute it, and the results record which was used.
    """
    occupied = pop > 0
    if occupied.sum() < deciles:
        return 0.0
    vals = pop[occupied]
    edges = np.quantile(vals, np.linspace(0, 1, deciles + 1))
    lo_mask = occupied & (pop <= edges[1])
    hi_mask = occupied & (pop >= edges[-2])
    if lo_mask.sum() == 0 or hi_mask.sum() == 0:
        return 0.0
    return float(field[hi_mask].mean() - field[lo_mask].mean())


def score(tmrt: np.ndarray, pop: np.ndarray, cost_usd: float = 0.0, threshold: float = TMRT_STRESS_C) -> Score:
    """Score one Tmrt field. `tmrt` may be a daylight-hour mean or a single hour."""
    over = np.clip(tmrt - threshold, 0, None)
    return Score(
        exposure=_pop_weighted_mean(tmrt, pop),
        excess=float((over * pop).sum()),
        people_at_risk=float(pop[tmrt > threshold].sum()),
        equity_gap=equity_gap(tmrt, pop),
        cost_usd=cost_usd,
    )


def exposure_by_threshold(tmrt: np.ndarray, pop: np.ndarray, thresholds: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Excess degree-hours and people above each threshold, from one sort of the field.

    Above a threshold t the people are the weight of the pixels hotter than t, and the excess is the
    weight-summed temperature of those pixels less t times their weight; both fall out of cumulative
    sums over the sorted field, so forty thresholds cost no more than one. Three arguments: the field,
    the weights, and the thresholds asked.
    """
    order = np.argsort(tmrt, axis=None)
    values = tmrt.ravel()[order].astype("float64")
    weights = pop.ravel()[order].astype("float64")
    weight_up_to = np.cumsum(weights)
    heat_up_to = np.cumsum(weights * values)
    below = np.searchsorted(values, np.asarray(thresholds, dtype="float64"), side="right")
    people = weight_up_to[-1] - np.where(below > 0, weight_up_to[np.maximum(below - 1, 0)], 0.0)
    heat = heat_up_to[-1] - np.where(below > 0, heat_up_to[np.maximum(below - 1, 0)], 0.0)
    return heat - np.asarray(thresholds, dtype="float64") * people, people


def benefit(baseline: Score, after: Score) -> dict:
    """Improvement of a plan over doing nothing."""
    d_excess = baseline.excess - after.excess
    return {
        "delta_exposure_C": round(baseline.exposure - after.exposure, 4),
        "delta_excess": round(d_excess, 2),
        "delta_people_at_risk": round(baseline.people_at_risk - after.people_at_risk, 1),
        "delta_equity_gap_C": round(baseline.equity_gap - after.equity_gap, 4),
        "cost_usd": round(after.cost_usd, 2),
        # The headline efficiency number: cooling bought per thousand dollars.
        "excess_reduced_per_1k_usd": round(d_excess / (after.cost_usd / 1000), 4) if after.cost_usd > 0 else 0.0,
    }
