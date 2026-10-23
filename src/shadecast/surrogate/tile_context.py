"""What every design of one tile shares: the loaded bundle and the baseline response."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class TileContext:
    bundle: Path
    out_dir: Path
    design_day: str
    kind: str
    canopy: np.ndarray
    umep_cover: np.ndarray
    feasible: np.ndarray
    profile: dict  # raster profile for writing the edited canopy
    baseline_tmrt: np.ndarray
    engine_threads: int | None
