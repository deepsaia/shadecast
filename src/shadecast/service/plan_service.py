"""Plan one intervention over a tile, simulate it, and score it against doing nothing."""

from __future__ import annotations

from ..pipeline import evaluate
from .city_catalog import CityCatalog
from .plan_outcome import PlanOutcome
from .plan_request import PlanRequest
from .progress_listener import ProgressListener

PHASE = "baseline physics, then the plan"


class PlanService:
    """The greedy plan for a budget, through the engine twice: as the tile is and as it would be."""

    def __init__(self, catalog: CityCatalog) -> None:
        self._catalog = catalog

    def plan(self, request: PlanRequest, progress: ProgressListener) -> PlanOutcome:
        paths = (
            self._catalog.tile_paths(request.target, request.tile)
            if request.tile is not None
            else self._catalog.densest_built(request.target)
        )
        progress.phase(PHASE)
        result = evaluate(paths.bundle, kind=request.kind, budget_usd=request.budget_usd)
        progress.finished(result)
        benefit = result.get("benefit", {})
        seconds = result.get("engine_seconds", {})
        return PlanOutcome(
            city=request.target,
            tile=paths.tile.id,
            kind=request.kind,
            budget_usd=request.budget_usd,
            cost_usd=float(result.get("plan", {}).get("cost_usd", 0.0)),
            pixels=int(result.get("pixels", 0)),
            exposure_drop=float(benefit.get("delta_exposure_C", 0.0)),
            people=round(float(benefit.get("delta_people_at_risk", 0.0))),
            efficiency=float(benefit.get("excess_reduced_per_1k_usd", 0.0)),
            engine_seconds=round(
                float(seconds.get("baseline", 0.0)) + float(seconds.get("plan", 0.0)), 1
            ),
            result=result,
        )
