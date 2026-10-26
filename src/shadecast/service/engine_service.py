"""Run the physics engine over the untouched tile once, and keep what it produced."""

from __future__ import annotations

from ..corpus.tile_paths import TilePaths
from ..surrogate.dataset import run_baseline_once
from .baseline_outcome import BaselineOutcome
from .baseline_request import BaselineRequest
from .city_catalog import CityCatalog
from .field_store import FieldStore
from .missing_stage import MissingStage
from .progress_listener import ProgressListener


class EngineService:
    """The baseline stage: the engine over a tile as it is, kept beside the bundle."""

    def __init__(self, catalog: CityCatalog) -> None:
        self._catalog = catalog

    def run_baseline(self, request: BaselineRequest, progress: ProgressListener) -> BaselineOutcome:
        paths = self._paths(request)
        design_day = str(FieldStore(paths).provenance().get("met", {}).get("design_day"))
        result = run_baseline_once(paths.bundle, paths.surrogate, design_day, progress)
        return BaselineOutcome(
            tile=paths.tile.id,
            design_day=design_day,
            destination=str(paths.baseline),
            seconds=round(result.seconds, 1) if result is not None else None,
            kept=result is None,
        )

    def _paths(self, request: BaselineRequest) -> TilePaths:
        if request.tile is not None:
            return self._catalog.tile_paths(request.target, request.tile)
        built = [
            tile for tile in self._catalog.ranked_on_disk(request.target) if tile.stages.bundle
        ]
        if not built:
            raise MissingStage("bundle", request.target, f"sdc build {request.target}")
        return self._catalog.tile_paths(request.target, built[0].tile)
