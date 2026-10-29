"""Answer a scenario from a tile's surrogate: the levers in, the outcomes and the cooling field out."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from ..corpus.tile_paths import TilePaths
from ..data.landcover import to_umep
from ..interventions import feasibility_mask
from ..interventions import priced
from ..interventions import spec_cost
from ..objectives import TMRT_STRESS_C
from ..surrogate.dataset import make_placement
from ..surrogate.predictor import Predictor
from ..surrogate.tile_surrogate import TileSurrogate
from .arrangements import family_of
from .assumptions import Assumptions
from .city_catalog import CityCatalog
from .field_store import FieldStore
from .model_catalog import WEIGHTS
from .model_catalog import ModelCatalog
from .plan_scoring import RESOLUTION_M
from .plan_scoring import PlanScoring
from .scenario import Scenario
from .scenario_answer import ScenarioAnswer
from .scenario_outcome import ScenarioOutcome
from .scenario_tile import ScenarioTile

SurrogateLoader = Callable[[Path, Path, Path], Predictor]

LIVE_KINDS = ("tree",)  # the kinds with a trained surrogate; the rest are coming soon
SEED = 7  # one fixed seed, so the same levers always give the same placement


class ScenarioService:
    """Loads what a tile needs the first time it is asked about and keeps it for every later scenario."""

    # Three collaborators: the catalog finds tiles, the model catalog finds their models, and the
    # loader turns a model and a tile into a predictor, which a test replaces with a fake.
    def __init__(
        self,
        catalog: CityCatalog,
        models: ModelCatalog,
        load: SurrogateLoader = TileSurrogate.load,
    ) -> None:
        self._catalog = catalog
        self._models = models
        self._load = load
        self._tiles: dict[Path, ScenarioTile] = {}

    def evaluate(self, scenario: Scenario) -> ScenarioAnswer:
        """The outcomes of the scenario against doing nothing, with the cooling field behind them."""
        if scenario.kind not in LIVE_KINDS:
            raise ValueError(f"{scenario.kind!r} has no surrogate yet; tree is the one live kind")
        tile = self._tile(scenario)
        judged = Assumptions(
            spec=priced(scenario.kind, scenario.unit_cost, scenario.maintenance),
            threshold=TMRT_STRESS_C if scenario.threshold is None else scenario.threshold,
        )
        placement = self._placement(scenario, tile, judged)
        cooling, seconds = tile.surrogate.predict(placement)
        gain = tile.scoring.benefit_of(placement, cooling, judged)
        baseline = tile.scoring.baseline(judged)
        outcome = ScenarioOutcome(
            city=tile.city,
            tile=tile.paths.tile.id,
            model_id=tile.model_id,
            kind=scenario.kind,
            arrangement=scenario.arrangement,
            coverage=round(float(placement.sum()) / max(1, int(tile.feasible.sum())), 4),
            tile_fraction=round(float(placement.mean()), 4),
            trees=int(placement.sum()),
            cost_usd=float(gain.get("cost_usd", 0.0)),
            unit_cost=judged.spec.unit_cost,
            maintenance=judged.spec.maintenance_frac,
            threshold=judged.threshold,
            baseline_exposure=baseline.exposure,
            baseline_at_risk=baseline.at_risk,
            exposure_drop=float(gain.get("delta_exposure_C", 0.0)),
            excess_removed=float(gain.get("delta_excess", 0.0)),
            people=round(float(gain.get("delta_people_at_risk", 0.0))),
            equity_gap_change=float(gain.get("delta_equity_gap_C", 0.0)),
            efficiency=float(gain.get("excess_reduced_per_1k_usd", 0.0)),
            surrogate_seconds=round(seconds, 3),
        )
        return ScenarioAnswer(outcome, cooling, placement)

    def _tile(self, scenario: Scenario) -> ScenarioTile:
        paths = self._paths(scenario)
        found = self._tiles.get(paths.root)
        if found is None:
            found = self._open(paths, scenario.kind)
            self._tiles[paths.root] = found
        return found

    def _paths(self, scenario: Scenario) -> TilePaths:
        if scenario.tile is not None:
            return self._catalog.tile_paths(scenario.target, scenario.tile)
        return self._catalog.densest_built(scenario.target)

    def _open(self, paths: TilePaths, kind: str) -> ScenarioTile:
        """Read the tile once: its newest model, the ground the kind may go on, and its scoring."""
        model = self._models.newest(paths.urban_centre)
        store = FieldStore(paths)
        heights = store.heights()
        return ScenarioTile(
            paths=paths,
            city=str(store.provenance().get("city", {}).get("key")),
            model_id=model.id,
            surrogate=self._load(Path(model.path) / WEIGHTS, paths.bundle, paths.physics),
            feasible=feasibility_mask(to_umep(store.land_cover(), heights), heights, kind),
            scoring=PlanScoring(store),
        )

    # Three arguments: the levers, the tile they act on, and the prices a budget is converted at.
    def _placement(self, scenario: Scenario, tile: ScenarioTile, judged: Assumptions) -> np.ndarray:
        coverage = scenario.coverage if scenario.coverage is not None else _coverage_bought(scenario, tile, judged)
        return make_placement(family_of(scenario.arrangement), tile.feasible, SEED, {"coverage": coverage})


# Three arguments: the budget comes from the levers, the feasible ground from the tile, the price from the
# assumptions.
def _coverage_bought(scenario: Scenario, tile: ScenarioTile, judged: Assumptions) -> float:
    """The share of the feasible ground a budget buys at the price per square metre."""
    per_pixel = spec_cost(judged.spec, np.ones((1, 1), dtype=bool), RESOLUTION_M)
    pixels = int(float(scenario.budget_usd or 0.0) // per_pixel)
    return min(1.0, pixels / max(1, int(tile.feasible.sum())))
