"""One layout for everything a tile produces, keyed by urban centre id and tile id.

``data/tiles/<uc_id>/<tile_id>/`` holds the bundle, the surrogate directory (the generated
responses, with the baseline physics in ``surrogate/baseline`` as it always has, so the
experiments keep reading it unchanged), the plans, and a results file. Models live apart, under
one root for all of them, ``data/models/<model id>/``, whatever tiles they learned from: their
manifests name the tiles. Status is read from the files that prove a stage ran, never from a
separate record: the directories are the record.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .tile import Tile
from .tile_stages import TileStages

TILES_ROOT = Path("data/tiles")
# Every model, from one tile or pooled over many, in one place with one reader.
MODELS_ROOT = Path("data/models")


@dataclass(frozen=True)
class TilePaths:
    tiles_root: Path
    urban_centre: int
    tile: Tile

    @property
    def root(self) -> Path:
        return Path(self.tiles_root) / str(self.urban_centre) / self.tile.id

    @property
    def bundle(self) -> Path:
        return self.root / "bundle"

    @property
    def surrogate(self) -> Path:
        return self.root / "surrogate"

    @property
    def baseline(self) -> Path:
        return self.surrogate / "baseline"

    @property
    def plans(self) -> Path:
        return self.root / "plans"

    @property
    def results(self) -> Path:
        return self.root / "results.json"

    @property
    def tiles_json(self) -> Path:
        return Path(self.tiles_root) / str(self.urban_centre) / "tiles.json"

    def stages(self) -> TileStages:
        """Which stages the tile directory proves.

        The model stage is not among them: models live under one root apart from the tiles, so
        the catalog sets it from their manifests with ``TileStages.with_model``.
        """
        return TileStages(
            bundle=(self.bundle / "provenance.json").exists(),
            baseline=(self.baseline / "tmrt_daylight.npy").exists(),
            physics=(self.surrogate / "manifest.json").exists(),
            results=self.results.exists(),
        )

    def as_dict(self) -> dict:
        return {
            "urban_centre": self.urban_centre,
            "tile": self.tile.id,
            "root": str(self.root),
            "bundle": str(self.bundle),
            "baseline": str(self.baseline),
            "surrogate": str(self.surrogate),
            "plans": str(self.plans),
            "results": str(self.results),
        }

    @classmethod
    def of_root(cls, root: Path) -> TilePaths:
        """The record for a tile directory ``<tiles root>/<urban centre id>/<tile id>``."""
        root = Path(root)
        return cls(root.parent.parent, int(root.parent.name), Tile.from_id(root.name))

    @classmethod
    def existing(cls, tiles_root: Path, urban_centre: int) -> list[TilePaths]:
        """Every tile directory present for an urban centre, in id order."""
        parent = Path(tiles_root) / str(urban_centre)
        if not parent.is_dir():
            return []
        found: list[TilePaths] = []
        for child in sorted(parent.iterdir()):
            if child.is_dir() and child.name.startswith("t"):
                found.append(cls(Path(tiles_root), urban_centre, Tile.from_id(child.name)))
        return found
