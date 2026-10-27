"""Every surrogate model that learned from an urban centre's tiles, per tile or pooled."""

from __future__ import annotations

from pathlib import Path

from ..corpus.tile_paths import TilePaths
from .json_file import read_object
from .missing_stage import MissingStage
from .model_summary import ModelSummary
from .unknown_model import UnknownModel

MODELS_ROOT = Path("data/models")
CHANNEL = "treeshade"
WEIGHTS = "model.pt"
MANIFEST = "manifest.json"


class ModelCatalog:
    """Answers which models exist for an urban centre and which is newest.

    Per-tile models live under each tile's ``models/``; pooled models live under one root and
    name the centre in their manifest. A directory with weights or a manifest is a model, so a
    half-copied one is visible rather than hidden.
    """

    def __init__(self, tiles_root: Path, models_root: Path) -> None:
        self._tiles_root = Path(tiles_root)
        self._models_root = Path(models_root)

    def models(self, urban_centre: int) -> list[ModelSummary]:
        """Every model of the centre, oldest first, across tile and pooled directories."""
        found = [
            _summary(model_dir, urban_centre, paths.tile.id)
            for paths in TilePaths.existing(self._tiles_root, urban_centre)
            for model_dir in _model_dirs(paths.models)
        ]
        found.extend(
            _summary(model_dir, urban_centre, None) for model_dir in self._pooled(urban_centre)
        )
        return sorted(found, key=_by_created)

    def models_across(self, urban_centres: list[int]) -> list[ModelSummary]:
        """Every model of the centres, oldest first, a pooled model once however many it serves."""
        by_path = {model.path: model for centre in urban_centres for model in self.models(centre)}
        return sorted(by_path.values(), key=_by_created)

    def newest(self, urban_centre: int) -> ModelSummary:
        found = self.models(urban_centre)
        if not found:
            raise MissingStage(
                "model", f"urban centre {urban_centre}", "sdc surrogate treeshade train <city>"
            )
        return found[-1]

    def named(self, urban_centre: int, model_id: str) -> ModelSummary:
        for model in self.models(urban_centre):
            if model.id == model_id:
                return model
        raise UnknownModel(urban_centre, model_id)

    def _pooled(self, urban_centre: int) -> list[Path]:
        if not self._models_root.is_dir():
            return []
        chosen = []
        for model_dir in sorted(self._models_root.iterdir()):
            tiles = read_object(model_dir / MANIFEST).get("data", {}).get("tiles", [])
            if any(entry.get("urban_centre") == urban_centre for entry in tiles):
                chosen.append(model_dir)
        return chosen


def model_created(model_dir: Path) -> str:
    """When a model was made, as ``YYYY-MM-DDTHH:MM:SS`` so models from any directory sort together.

    From the manifest when there is one, else from the directory name, which ends in a
    compact timestamp such as ``20261023T121739``.
    """
    created = read_object(Path(model_dir) / MANIFEST).get("created")
    if created:
        return str(created)[:19]
    stamp = Path(model_dir).name.rsplit("-", 1)[-1]
    if len(stamp) == 15 and stamp[8] == "T" and stamp.replace("T", "").isdigit():
        return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}"
    return Path(model_dir).name


def _model_dirs(models: Path) -> list[Path]:
    if not models.is_dir():
        return []
    return sorted(
        child
        for child in models.iterdir()
        if child.is_dir() and ((child / WEIGHTS).exists() or (child / MANIFEST).exists())
    )


def _summary(model_dir: Path, urban_centre: int, tile: str | None) -> ModelSummary:
    manifest = read_object(model_dir / MANIFEST)
    tiles = manifest.get("data", {}).get("tiles", [])
    return ModelSummary(
        id=model_dir.name,
        urban_centres=_centres_of(tiles) or [urban_centre],
        created=model_created(model_dir),
        channel=CHANNEL,
        tile=tile,
        path=str(model_dir),
        has_weights=(model_dir / WEIGHTS).exists(),
        has_manifest=bool(manifest),
        skill=manifest.get("metrics", {}).get("best_skill"),
        tiles_trained=len(tiles) if tiles else 1,
        manifest=manifest,
    )


def _centres_of(tiles: list[dict]) -> list[int]:
    """The distinct urban centres a manifest's training tiles came from, in order."""
    return list(
        dict.fromkeys(
            int(entry.get("urban_centre")) for entry in tiles if entry.get("urban_centre")
        )
    )


def _by_created(model: ModelSummary) -> str:
    return model.created
