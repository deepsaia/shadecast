"""The outcome curves of a tile, computed once per tile and model and kept beside the tile.

The surrogate is run over a ladder of coverages in every arrangement, and the stored engine designs
are scored on the same axes. The result is written as a derived file stamped with the model's weights,
the physics manifest and the baseline, so a new model or new physics regenerates it and nothing else
does. Prices never enter the four outcomes it holds, so it does not depend on the assumptions; the
threshold does, so the two threshold-bound outcomes are kept at every whole degree from 30 to 70 C.
"""

from __future__ import annotations

import time
from datetime import UTC
from datetime import datetime
from pathlib import Path

from ..surrogate.dataset import make_placement
from .arrangements import ARRANGEMENTS
from .arrangements import arrangement_of
from .arrangements import family_of
from .derived_cache import DerivedCache
from .field_store import FieldStore
from .scenario_service import SEED
from .scenario_service import ScenarioService
from .scenario_tile import ScenarioTile
from .sweep import Sweep
from .sweep_curve import SweepCurve
from .sweep_design import SweepDesign
from .sweep_point import SweepPoint
from .tile_reporter import DERIVED

COVERAGES = (0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
THRESHOLDS = tuple(float(degrees) for degrees in range(30, 71))
NAME = "sweep"


class SweepService:
    """Answers a tile's sweep from disk when it is current, else computes and keeps it."""

    def __init__(self, scenarios: ScenarioService) -> None:
        self._scenarios = scenarios

    def sweep(self, target: str, tile: str | None) -> Sweep:
        opened = self._scenarios.open_tile(target, tile)
        cache = DerivedCache(opened.paths.root / DERIVED)
        sources = _sources(opened)
        if cache.current(NAME, sources):
            return Sweep.model_validate({**cache.read(NAME), "fresh": False})
        computed = compute(opened)
        cache.write(NAME, computed.model_dump(), sources)
        return computed


def _sources(opened: ScenarioTile) -> list[Path]:
    """What the sweep is derived from: the model's weights, the designs the engine ran, the baseline."""
    return [opened.weights, opened.paths.physics / "manifest.json", opened.paths.baseline / "tmrt_daylight.npy"]


def compute(opened: ScenarioTile) -> Sweep:
    """The surrogate along the ladder in every arrangement, and the engine designs on the same axes."""
    started = time.perf_counter()
    curves = [
        SweepCurve(arrangement=arrangement, points=[_point(opened, arrangement, coverage) for coverage in COVERAGES])
        for arrangement in ARRANGEMENTS
    ]
    store = FieldStore(opened.paths)
    designs = [_design(opened, store, design_id) for design_id in store.design_ids() if arrangement_of(design_id)]
    return Sweep(
        model_id=opened.model_id,
        created=datetime.now(UTC).isoformat(timespec="seconds"),
        coverages=list(COVERAGES),
        thresholds=list(THRESHOLDS),
        curves=curves,
        designs=designs,
        seconds=round(time.perf_counter() - started, 1),
    )


# Three arguments: the tile, and the two levers that place the trees on it.
def _point(opened: ScenarioTile, arrangement: str, coverage: float) -> SweepPoint:
    placement = make_placement(family_of(arrangement), opened.feasible, SEED, {"coverage": coverage})
    cooling, _ = opened.surrogate.predict(placement)
    return opened.scoring.point_over(cooling, THRESHOLDS)


# Three arguments: the tile, the store its designs are read from, and which design.
def _design(opened: ScenarioTile, store: FieldStore, design_id: str) -> SweepDesign:
    placement, response = store.response(design_id)
    return SweepDesign(
        id=design_id,
        arrangement=arrangement_of(design_id),
        coverage=round(float(placement.sum()) / max(1, int(opened.feasible.sum())), 4),
        point=opened.scoring.point_over(response, THRESHOLDS),
    )
