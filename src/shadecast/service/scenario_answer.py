"""A scenario's outcomes with the two fields they came from, for a map beside the numbers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .scenario_outcome import ScenarioOutcome


@dataclass(frozen=True)
class ScenarioAnswer:
    outcome: ScenarioOutcome
    cooling: np.ndarray  # predicted drop in the daylight mean radiant temperature, degrees C
    placement: np.ndarray  # True where the intervention goes
