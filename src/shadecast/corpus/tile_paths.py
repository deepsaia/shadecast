"""One layout for everything a tile produces, keyed by urban centre id and tile id.

``data/tiles/<uc_id>/<tile_id>/`` holds the bundle, the surrogate directory (which carries the
baseline physics in ``surrogate/baseline`` as it always has, so the experiments and the
walkthrough keep reading it unchanged), the plans, and a results file. Status is read from the
files that prove a stage ran, never from a separate record: the directories are the record.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .tile import Tile

TILES_ROOT = Path("data/tiles")


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

    def stages(self) -> dict[str, bool]:
        """Which stages have run, from the files that prove it."""
        return {
            "bundle": (self.bundle / "provenance.json").exists(),
            "baseline": (self.baseline / "tmrt_daylight.npy").exists(),
            "surrogate": (self.surrogate / "manifest.json").exists(),
            "model": (self.surrogate / "model.pt").exists(),
            "results": self.results.exists(),
        }

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
