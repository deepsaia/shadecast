"""What a scenario needs from a surrogate: a placement in, the cooling field and its seconds out."""

from __future__ import annotations

from typing import Protocol

import numpy as np


class Predictor(Protocol):
    def predict(self, placement: np.ndarray) -> tuple[np.ndarray, float]: ...
