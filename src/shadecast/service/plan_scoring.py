"""Score every simulated design of a tile against doing nothing, as the simulator ranks plans."""

from __future__ import annotations

from functools import cached_property

import numpy as np

from ..exposure import outdoor_mask
from ..exposure import outdoor_weights
from ..interventions import spec_cost
from ..objectives import Score
from ..objectives import benefit
from ..objectives import exposure_by_threshold
from ..objectives import score
from .arrangements import arrangement_of
from .assumptions import Assumptions
from .baseline_score import BaselineScore
from .field_store import FieldStore
from .physics_facts import PhysicsFacts
from .plan import Plan
from .sweep_point import SweepPoint
from .tile_layers import TileLayers

KIND = "tree"
RESOLUTION_M = 1.0
# What the stored designs are judged with, so they are all judged alike: the catalogue's prices, the project's line.
JUDGED_ALIKE = Assumptions.catalogue(KIND)


class PlanScoring:
    """The baseline score of a tile and every design of a known arrangement scored against it."""

    def __init__(self, store: FieldStore) -> None:
        self._store = store
        self._baselines: dict[float, Score] = {}
        self._baseline_curves: dict[tuple[float, ...], tuple[np.ndarray, np.ndarray]] = {}

    def baseline(self, assumptions: Assumptions = JUDGED_ALIKE) -> BaselineScore:
        scored = self._baseline_at(assumptions.threshold)
        return BaselineScore(exposure=round(scored.exposure, 2), at_risk=round(scored.people_at_risk))

    def plans(self) -> list[Plan]:
        """Every plan, by arrangement then coverage, so like compares with like."""
        plans = [self._plan(design_id) for design_id in self._store.design_ids() if arrangement_of(design_id)]
        return sorted(plans, key=_by_arrangement_then_coverage)

    # Three arguments: the placement, the cooling it causes, and what it is judged with, which defaults
    # to the catalogue's prices and the project's threshold so the stored designs are all judged alike.
    def benefit_of(self, placement: np.ndarray, response: np.ndarray, assumptions: Assumptions = JUDGED_ALIKE) -> dict:
        """What a placement buys, given the cooling it causes, against doing nothing; cost included."""
        spent = spec_cost(assumptions.spec, placement, RESOLUTION_M)
        after = self._score(self._layers.baseline - response, spent, assumptions.threshold)
        return benefit(self._baseline_at(assumptions.threshold), after)

    def point_over(self, response: np.ndarray, thresholds: tuple[float, ...]) -> SweepPoint:
        """A placement's four price-free outcomes against doing nothing, the threshold-bound two at every threshold."""
        after = self._layers.baseline - response
        before_excess, before_people = self._baseline_over(thresholds)
        excess, people = exposure_by_threshold(self._outdoors(after), self._layers.weights, np.asarray(thresholds))
        base = self._baseline_at(thresholds[0])
        scored = self._score(after, 0.0, thresholds[0])
        return SweepPoint(
            exposure_drop=round(base.exposure - scored.exposure, 4),
            equity_gap_change=round(base.equity_gap - scored.equity_gap, 4),
            excess_removed=np.round(before_excess - excess, 2).tolist(),
            people=np.round(before_people - people, 1).tolist(),
        )

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

    def _baseline_over(self, thresholds: tuple[float, ...]) -> tuple[np.ndarray, np.ndarray]:
        """Doing nothing at every threshold asked, computed once per set of thresholds."""
        found = self._baseline_curves.get(thresholds)
        if found is None:
            found = exposure_by_threshold(
                self._outdoors(self._layers.baseline), self._layers.weights, np.asarray(thresholds)
            )
            self._baseline_curves[thresholds] = found
        return found

    def _outdoors(self, field: np.ndarray) -> np.ndarray:
        return np.where(self._layers.outdoor, field, 0)

    def _baseline_at(self, threshold: float) -> Score:
        """Doing nothing, judged at a threshold, scored once per threshold asked."""
        found = self._baselines.get(threshold)
        if found is None:
            found = self._score(self._layers.baseline, 0.0, threshold)
            self._baselines[threshold] = found
        return found

    def _plan(self, design_id: str) -> Plan:
        placement, response = self._store.response(design_id)
        gain = self.benefit_of(placement, response)
        spent = float(gain.get("cost_usd", 0.0))
        return Plan(
            id=design_id,
            arrangement=arrangement_of(design_id),
            coverage=round(float(placement.mean()), 4),
            trees=int(placement.sum()),
            cost_usd=spent,
            cost_m=round(spent / 1e6, 2),
            exposure_drop=float(gain.get("delta_exposure_C", 0.0)),
            people=round(float(gain.get("delta_people_at_risk", 0.0))),
            efficiency=float(gain.get("excess_reduced_per_1k_usd", 0.0)),
        )

    # Three arguments: the field, what it cost, and the threshold it is judged at.
    def _score(self, field: np.ndarray, spent: float, threshold: float) -> Score:
        return score(self._outdoors(field), self._layers.weights, spent, threshold)


def _by_arrangement_then_coverage(plan: Plan) -> tuple[str, float]:
    return (plan.arrangement, plan.coverage)
