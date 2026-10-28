"""Score every simulated design of a tile against doing nothing, as the benchmark ranks plans."""

from __future__ import annotations

from functools import cached_property

import numpy as np

from ..exposure import outdoor_mask, outdoor_weights
from ..interventions import cost
from ..objectives import Score, benefit, score
from .baseline_score import BaselineScore
from .field_store import FieldStore
from .physics_facts import PhysicsFacts
from .plan import Plan
from .tile_layers import TileLayers

# The design families that are plans, by the first word of their id. Sparse probes exist to
# characterize the response kernel and are not candidate plans.
ARRANGEMENT = {"clustered": "clustered", "random": "scattered", "corridor": "corridor"}
KIND = "tree"
RESOLUTION_M = 1.0


class PlanScoring:
    """The baseline score of a tile and every design of a known arrangement scored against it."""

    def __init__(self, store: FieldStore) -> None:
        self._store = store

    def baseline(self) -> BaselineScore:
        scored = self._score(self._layers.baseline, 0.0)
        return BaselineScore(
            exposure=round(scored.exposure, 2), at_risk=round(scored.people_at_risk)
        )

    def plans(self) -> list[Plan]:
        """Every plan, by arrangement then coverage, so like compares with like."""
        baseline = self._score(self._layers.baseline, 0.0)
        plans = [
            self._plan(design_id, baseline)
            for design_id in self._store.design_ids()
            if _family(design_id) in ARRANGEMENT
        ]
        return sorted(plans, key=_by_arrangement_then_coverage)

    def physics(self) -> PhysicsFacts:
        """How many designs the engine ran and how long each took, from the manifest."""
        seconds = [float(entry.get("engine_seconds", 0)) for entry in self._store.manifest()]
        return PhysicsFacts(
            designs=len(seconds),
            engine_minutes=round(sum(seconds) / 60, 1),
            seconds_per_design_min=round(min(seconds)) if seconds else 0,
            seconds_per_design_max=round(max(seconds)) if seconds else 0,
        )

    @cached_property
    def _layers(self) -> TileLayers:
        heights = self._store.heights()
        return TileLayers(
            outdoor=outdoor_mask(heights),
            weights=outdoor_weights(self._store.population(), heights),
            baseline=self._store.baseline_daylight(),
        )

    def _plan(self, design_id: str, baseline: Score) -> Plan:
        placement, response = self._store.response(design_id)
        spent = cost(KIND, placement, RESOLUTION_M)
        gain = benefit(baseline, self._score(self._layers.baseline - response, spent))
        return Plan(
            id=design_id,
            arrangement=ARRANGEMENT.get(_family(design_id), ""),
            coverage=round(float(placement.mean()), 4),
            trees=int(placement.sum()),
            cost_usd=round(spent, 2),
            cost_m=round(spent / 1e6, 2),
            exposure_drop=float(gain.get("delta_exposure_C", 0.0)),
            people=round(float(gain.get("delta_people_at_risk", 0.0))),
            efficiency=float(gain.get("excess_reduced_per_1k_usd", 0.0)),
        )

    def _score(self, field: np.ndarray, spent: float) -> Score:
        return score(np.where(self._layers.outdoor, field, 0), self._layers.weights, spent)


def _family(design_id: str) -> str:
    return design_id.split("_", maxsplit=1)[0]


def _by_arrangement_then_coverage(plan: Plan) -> tuple[str, float]:
    return (plan.arrangement, plan.coverage)
