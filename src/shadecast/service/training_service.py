"""Fit a surrogate for a city's tiles, or several pooled, and write it under the models root.

A finished model directory holds the weights, the manifest and the training curve. The start
record exists only while the run is unfinished, so the runs table can name it.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from ..corpus import tile_lookup
from ..corpus.tile_selection import TileSelection
from ..surrogate import manifest
from ..surrogate.features import CHANNEL_SETS
from ..surrogate.manifest_inputs import ManifestInputs
from ..surrogate.patch_set import PatchSet
from ..surrogate.patch_settings import PatchSettings
from ..surrogate.patches import crop_batch
from ..surrogate.patches import crop_cities
from ..surrogate.training import train
from ..surrogate.training_settings import TrainingSettings
from ..surrogate.training_state import CHECKPOINT_NAME
from ..surrogate.training_state import STARTED_NAME
from .model_catalog import model_created
from .progress_listener import ProgressListener
from .training_outcome import TrainingOutcome
from .training_request import TrainingRequest

PATCHES = "patches"
CROPPING = "cropping patches"
WEIGHTS = "model.pt"


class TrainingService:
    """Chooses the tiles a request means, crops their patches, fits the model and records it."""

    def __init__(self, tiles_root: Path, models_root: Path) -> None:
        self._tiles_root = Path(tiles_root)
        self._models_root = Path(models_root)

    def pairs_for(self, request: TrainingRequest) -> list[tuple[Path, Path]]:
        """(physics directory, bundle) per tile: a city's tiles with physics, a pair, or pairs.

        A city key alone means every tile with physics, narrowed by named tiles or a selection.
        """
        pairs: list[tuple[Path, Path]] = []
        for item in request.pair:
            if "=" in item:
                left, right = item.split("=", 1)
                pairs.append((Path(left), Path(right)))
            else:
                found = tile_lookup.simulated_tiles(item, None, self._tiles_root)
                pairs.extend((paths.physics, paths.bundle) for paths in found)
        if request.target is not None and request.bundle is not None:
            pairs.append((Path(request.target), request.bundle))
        elif request.target is not None:
            selection = TileSelection(request.densest, request.stratified)
            found = tile_lookup.simulated_tiles(request.target, request.tiles, self._tiles_root, selection)
            pairs.extend((paths.physics, paths.bundle) for paths in found)
        if not pairs:
            raise ValueError("give a city key, PHYSICS_DIR and BUNDLE, or one or more --pair")
        return pairs

    def train(self, request: TrainingRequest, progress: ProgressListener) -> TrainingOutcome:
        """Crop, fit, and write the weights, the report and the manifest where the model belongs."""
        pairs = self.pairs_for(request)
        if request.holdout_city and len(pairs) < 2:
            raise ValueError("a city holdout needs at least two cities")
        if request.channels not in CHANNEL_SETS:
            raise ValueError(f"channels must be one of {sorted(CHANNEL_SETS)}")
        patch_settings = PatchSettings(size=request.patch, per_entry=request.per_entry, channels=request.channels)
        progress.phase(CROPPING)
        started = time.time()
        inputs, targets, origins = _crop(pairs, patch_settings)
        progress.step_done(
            PATCHES,
            round(time.time() - started, 1),
            {
                "patches": len(inputs),
                "designs": len(set(origins)),
                "tiles": len(pairs),
                "patch_px": request.patch,
            },
        )
        created = manifest.now()
        destination, model_id, resumed = self._destination(request, pairs, created)
        destination.mkdir(parents=True, exist_ok=True)
        _record_start(destination, pairs, created)
        settings = TrainingSettings(
            epochs=request.epochs, holdout_city=request.holdout_city, channels=request.channels
        )
        report = train(PatchSet(inputs, targets, origins), settings, destination / WEIGHTS, progress)
        report: dict = {
            **report,
            "patch_px": request.patch,
        }
        manifest.save_epochs(report.get("history", []), destination / manifest.EPOCHS_FILE)
        inputs_for_manifest = ManifestInputs(
            model_id=model_id,
            created=created.isoformat(timespec="seconds"),
            pairs=pairs,
            report=report,
            patch_px=request.patch,
            per_entry=request.per_entry,
            model_path=destination / WEIGHTS,
        )
        manifest.write(destination, manifest.build(inputs_for_manifest))
        (destination / STARTED_NAME).unlink(missing_ok=True)  # the manifest now says it all
        return TrainingOutcome(
            model_id=model_id,
            destination=str(destination),
            resumed=resumed,
            patches=len(inputs),
            designs=len(set(origins)),
            cities=len(pairs),
            skill=float(report.get("final_skill", 0.0)),
            mae_c=float(report.get("final_test_mae_C", 0.0)),
            zero_mae_c=float(report.get("zero_baseline_mae_C", 0.0)),
            beats_nothing=bool(report.get("beats_predicting_nothing", False)),
            holdout_mode=str(report.get("holdout_mode", "")),
            best_epoch=int(report.get("best_epoch", 0)),
            last_epoch=int(report.get("last_epoch", 0)),
            interrupted=bool(report.get("interrupted", False)),
            report=report,
        )

    def _destination(
        self, request: TrainingRequest, pairs: list[tuple[Path, Path]], created: datetime
    ) -> tuple[Path, str, bool]:
        if request.resume:
            unfinished = unfinished_model(self._models_root)
            if unfinished is None:
                raise ValueError(f"nothing to resume under {self._models_root}")
            return unfinished, unfinished.name, True
        model_id = manifest.new_model_id(pairs, created)
        return self._models_root / model_id, model_id, False


def _record_start(destination: Path, pairs: list[tuple[Path, Path]], created: datetime) -> None:
    """Write which tiles the run trains on before it starts, so an unfinished run can be named.

    A resumed run keeps the record of its first start; the manifest replaces it at the end.
    """
    record = destination / STARTED_NAME
    if record.exists():
        return
    started = {
        "started": created.isoformat(timespec="seconds"),
        "cities": manifest.city_keys(pairs),
        "tiles": [manifest.tile_ref(bundle) for _, bundle in pairs],
    }
    record.write_text(json.dumps(started, indent=2))


def unfinished_model(root: Path) -> Path | None:
    """The newest model directory with a checkpoint and no manifest, else None."""
    if not Path(root).is_dir():
        return None
    candidates = [
        child
        for child in Path(root).iterdir()
        if (child / CHECKPOINT_NAME).exists() and not (child / manifest.MANIFEST_FILE).exists()
    ]
    return max(candidates, key=model_created) if candidates else None


def _crop(pairs: list[tuple[Path, Path]], settings: PatchSettings) -> tuple[np.ndarray, np.ndarray, list[str]]:
    if len(pairs) == 1:
        return crop_batch(pairs[0][0], pairs[0][1], settings)
    return crop_cities(pairs, settings)
