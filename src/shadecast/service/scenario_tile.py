"""Everything the simulator keeps about one tile between scenarios: model, feasible ground, scoring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..corpus.tile_paths import TilePaths
from ..surrogate.predictor import Predictor
from .plan_scoring import PlanScoring


@dataclass(frozen=True)
class ScenarioTile:
    paths: TilePaths
    city: str
    model_id: str
    weights: Path  # the checkpoint the surrogate was loaded from, which stamps what is derived from it
    surrogate: Predictor
    feasible: np.ndarray  # where the kind may be placed, as the physics designs were drawn
    scoring: PlanScoring
