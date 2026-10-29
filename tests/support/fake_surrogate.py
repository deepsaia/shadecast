"""A surrogate that cools every planted pixel by a fixed amount and nothing else, and counts its loads."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import numpy as np

COOLING_C = 2.0


class FakeSurrogate:
    loads: ClassVar[list[tuple[Path, Path, Path]]] = []
    predictions: ClassVar[int] = 0

    @classmethod
    def load(cls, checkpoint: Path, bundle: Path, physics_dir: Path) -> FakeSurrogate:
        cls.loads.append((checkpoint, bundle, physics_dir))
        return cls()

    def predict(self, placement: np.ndarray) -> tuple[np.ndarray, float]:
        FakeSurrogate.predictions += 1
        return placement.astype("float32") * COOLING_C, 0.01
