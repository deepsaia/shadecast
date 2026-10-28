"""Run the pre-registered experiments over the cities' tiles that have a baseline."""

from __future__ import annotations

from pathlib import Path

from ..experiments.channel import run_channel
from ..experiments.factorial import run_factorial
from ..experiments.targeting import run_targeting
from .city_catalog import CityCatalog
from .experiment_outcome import ExperimentOutcome
from .experiment_request import ExperimentRequest
from .missing_stage import MissingStage
from .progress_listener import ProgressListener

FACTORIAL, TARGETING, CHANNEL = "factorial", "targeting", "channel"
NAMES = (FACTORIAL, TARGETING, CHANNEL)
Corpus = list[tuple[str, Path, Path]]


class ExperimentService:
    """Pairs each city's densest tile with a baseline to its physics and runs the experiment."""

    def __init__(self, catalog: CityCatalog, data_root: Path) -> None:
        self._catalog = catalog
        self._data_root = Path(data_root)

    def run(self, request: ExperimentRequest, progress: ProgressListener) -> ExperimentOutcome:
        if not request.cities:
            raise ValueError("give at least one city")
        if request.name not in NAMES:
            raise ValueError(f"unknown experiment {request.name!r}; one of {', '.join(NAMES)}")
        corpus = [self._entry(key) for key in request.cities]
        out = request.out if request.out is not None else self._data_root / f"{request.name}.json"
        plural = "s" if len(corpus) != 1 else ""
        progress.phase(f"{request.name} over {len(corpus)} tile{plural}")
        rows, verdict = _run(request, corpus, out)
        progress.finished({"name": request.name, "rows": rows, "out": str(out)})
        return ExperimentOutcome(name=request.name, out=str(out), rows=rows, verdict=verdict)

    def _entry(self, key: str) -> tuple[str, Path, Path]:
        """The city's densest tile with a baseline, labeled by key and tile."""
        built = [tile for tile in self._catalog.ranked_on_disk(key) if tile.stages.bundle]
        if not built:
            raise MissingStage("bundle", key, f"sdc build {key}")
        ready = [tile for tile in built if tile.stages.baseline]
        if not ready:
            raise MissingStage("baseline", key, f"sdc simulate baseline {key}")
        paths = self._catalog.tile_paths(key, ready[0].tile)
        return f"{key}-{paths.tile.id}", paths.bundle, paths.physics


def _run(request: ExperimentRequest, corpus: Corpus, out: Path) -> tuple[int, dict]:
    if request.name == FACTORIAL:
        return len(run_factorial(corpus, out)), {}
    if request.name == TARGETING:
        result = run_targeting(corpus, out, budget=request.budget)
    else:
        result = run_channel(corpus, out, budget=request.budget)
    return len(result.get("rows", [])), dict(result.get("verdict", {}))
