"""Run the designed experiments through the physics engine for a city's tiles."""

from __future__ import annotations

import time

from ..corpus.tile_paths import TilePaths
from ..surrogate.dataset import default_plan, generate
from ..surrogate.generation_settings import GenerationSettings
from .city_catalog import CityCatalog
from .generation_outcome import GenerationOutcome
from .generation_request import GenerationRequest
from .missing_stage import MissingStage
from .progress_listener import ProgressListener

ALL = "all"


class GenerationService:
    """Chooses the tiles a request means and runs the generator over one tile at a time."""

    def __init__(self, catalog: CityCatalog) -> None:
        self._catalog = catalog

    def tiles_for(self, request: GenerationRequest) -> list[TilePaths]:
        """The built tiles the request means, densest first: one, the named ones, or all."""
        built = [
            tile for tile in self._catalog.ranked_on_disk(request.target) if tile.stages.bundle
        ]
        if not built:
            raise MissingStage("bundle", request.target, f"sdc build {request.target}")
        if request.tiles is None:
            chosen = [built[0].tile]
        elif request.tiles.strip().lower() in ("", ALL):
            chosen = [tile.tile for tile in built]
        else:
            chosen = _named(request, [tile.tile for tile in built])
        if request.out is not None and len(chosen) > 1:
            raise ValueError("an output directory applies to one tile")
        return [self._catalog.tile_paths(request.target, tile_id) for tile_id in chosen]

    def generate(
        self, paths: TilePaths, request: GenerationRequest, progress: ProgressListener
    ) -> GenerationOutcome:
        """Every design of the plan through the engine for one tile; designs on disk are kept."""
        destination = request.out if request.out is not None else paths.physics
        started = time.time()
        summary = generate(paths.bundle, destination, settings_for(request), progress)
        return GenerationOutcome(
            tile=paths.tile.id,
            destination=str(destination),
            entries=int(summary.get("entries", 0)),
            seconds=round(time.time() - started, 1),
        )


def settings_for(request: GenerationRequest) -> GenerationSettings:
    return GenerationSettings(plan=default_plan(), kind=request.kind, jobs=request.jobs)


def _named(request: GenerationRequest, built: list[str]) -> list[str]:
    chosen = [part.strip() for part in str(request.tiles).split(",") if part.strip()]
    for tile_id in chosen:
        if tile_id not in built:
            raise MissingStage(
                "bundle",
                f"{request.target} tile {tile_id}",
                f"sdc build {request.target} --tiles {tile_id}",
            )
    return chosen
