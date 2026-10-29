"""What is simulating or training now, read from the locks and checkpoints the operations leave."""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path

from ..corpus.tile_paths import TilePaths
from ..corpus.tile_ref import tile_of
from ..surrogate.dataset import SIMULATION_LOCK
from ..surrogate.dataset import default_plan
from ..surrogate.dataset import lock_is_stale
from ..surrogate.training_state import CHECKPOINT_NAME
from ..surrogate.training_state import STARTED_NAME
from .city_catalog import CityCatalog
from .field_store import RESPONSE_ARCHIVE
from .json_file import read_object
from .model_catalog import MANIFEST
from .run_summary import RunSummary

SIMULATION = "simulation"
TRAINING = "training"
UNRECORDED = "unrecorded"


class RunStatus:
    """Answers which runs are in progress: simulation per tile, training under the models root."""

    def __init__(self, catalog: CityCatalog, models_root: Path) -> None:
        self._catalog = catalog
        self._models_root = Path(models_root)

    def runs(self) -> list[RunSummary]:
        found: list[RunSummary] = []
        for city in self._catalog.cities():
            for tile in self._catalog.tiles_on_disk(city.key):
                paths = self._catalog.tile_paths(city.key, tile.tile)
                lock = paths.physics / SIMULATION_LOCK
                if lock.exists():
                    found.append(_simulation(city.key, paths, lock))
        found.extend(_training(model_dir) for model_dir in _unfinished(self._models_root))
        return found


def _simulation(city: str, paths: TilePaths, lock: Path) -> RunSummary:
    done = sum(1 for child in paths.physics.iterdir() if (child / RESPONSE_ARCHIVE).exists())
    return RunSummary(
        kind=SIMULATION,
        city=city,
        tile=paths.tile.id,
        model=None,
        started=_stamp(lock),
        alive=not lock_is_stale(lock),
        designs_done=done,
        designs_planned=len(default_plan()),
    )


def _training(model_dir: Path) -> RunSummary:
    """An unfinished run, named for the tiles its start record lists; older runs left none."""
    record = read_object(model_dir / STARTED_NAME)
    tiles = [str(ref) for ref in record.get("tiles", [])]
    cities = [str(city) for city in record.get("cities", [])]
    return RunSummary(
        kind=TRAINING,
        city=", ".join(cities) or UNRECORDED,
        tile=tile_of(tiles[0]) if len(tiles) == 1 else None,
        model=model_dir.name,
        started=str(record.get("started") or _stamp(model_dir / CHECKPOINT_NAME)),
        alive=None,
        designs_done=None,
        designs_planned=None,
    )


def _unfinished(models: Path) -> list[Path]:
    """Model directories with a checkpoint and no manifest: training that has not finished."""
    if not models.is_dir():
        return []
    return sorted(
        child for child in models.iterdir() if (child / CHECKPOINT_NAME).exists() and not (child / MANIFEST).exists()
    )


def _stamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds")
