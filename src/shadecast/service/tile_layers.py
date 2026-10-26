"""The three arrays every score of a tile is computed from."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TileLayers:
    outdoor: np.ndarray  # True where there is no building
    weights: np.ndarray  # residents redistributed onto the outdoor pixels within reach of home
    baseline: np.ndarray  # the daylight mean radiant temperature of doing nothing, degrees C
