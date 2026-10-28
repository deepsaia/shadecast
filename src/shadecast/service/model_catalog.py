"""Every surrogate model under one root, attributed to urban centres by its manifest."""

from __future__ import annotations

from pathlib import Path

from ..corpus.tile_ref import centre_of, tile_of
from .json_file import read_object
from .missing_stage import MissingStage
from .model_summary import ModelSummary
from .unknown_model import UnknownModel

CHANNEL = "treeshade"
WEIGHTS = "model.pt"
MANIFEST = "manifest.json"


class ModelCatalog:
    """Answers which models exist, which learned from an urban centre, and which is newest.

    Every model lives under one root whatever it learned from, and its manifest records the tiles
    it was trained on as ``<urban centre id>/<tile id>`` references. Membership is read from the
    manifest, never from where a directory sits. A directory with weights but no manifest is
    listed too, belonging to no centre: training that did not finish, or a half copy, visible
    rather than hidden.
    """

    def __init__(self, models_root: Path) -> None:
        self._models_root = Path(models_root)

    def all_models(self) -> list[ModelSummary]:
        """Every model under the root, oldest first."""
        found = [_summary(model_dir) for model_dir in _model_dirs(self._models_root)]
        return sorted(found, key=_by_created)

    def models(self, urban_centre: int) -> list[ModelSummary]:
        """The models that learned from the centre's tiles, oldest first."""
        return [model for model in self.all_models() if urban_centre in model.urban_centres]

    def tiles_with_models(self, urban_centre: int) -> set[str]:
        """The centre's tiles that some finished model learned from."""
        return {
            tile_of(ref)
            for model in self.all_models()
            for ref in _tiles_of(model.manifest)
            if centre_of(ref) == urban_centre
        }

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


def model_created(model_dir: Path) -> str:
    """When a model was made, as ``YYYY-MM-DDTHH:MM:SS`` so every model sorts by the same clock.

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


def _model_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        child
        for child in root.iterdir()
        if child.is_dir() and ((child / WEIGHTS).exists() or (child / MANIFEST).exists())
    )


def _summary(model_dir: Path) -> ModelSummary:
    manifest = read_object(model_dir / MANIFEST)
    tiles = _tiles_of(manifest)
    return ModelSummary(
        id=model_dir.name,
        urban_centres=_centres_of(tiles),
        created=model_created(model_dir),
        channel=CHANNEL,
        tile=_only_tile(tiles),
        path=str(model_dir),
        has_weights=(model_dir / WEIGHTS).exists(),
        has_manifest=bool(manifest),
        skill=manifest.get("metrics", {}).get("best_skill"),
        tiles_trained=len(tiles),
        manifest=manifest,
    )


def _tiles_of(manifest: dict) -> list[str]:
    return [str(ref) for ref in manifest.get("data", {}).get("tiles", [])]


def _only_tile(tiles: list[str]) -> str | None:
    """The one tile a model learned from, or None for a pooled model or an unrecorded one."""
    return tile_of(tiles[0]) if len(tiles) == 1 else None


def _centres_of(tiles: list[str]) -> list[int]:
    """The distinct urban centres a manifest's training tiles came from, in order."""
    return list(dict.fromkeys(centre_of(ref) for ref in tiles))


def _by_created(model: ModelSummary) -> str:
    return model.created
