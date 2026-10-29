"""Assemble tile bundles from open sources into the tile layout, one tile at a time."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from ..cities import City
from ..corpus.tile import Tile
from ..corpus.tile_paths import TilePaths
from .build_outcome import BuildOutcome
from .build_request import BuildRequest
from .build_target import BuildTarget
from .built_tile import BuiltTile
from .city_catalog import CityCatalog
from .progress_listener import ProgressListener
from .tile_choice import chosen_tiles
from .tile_choice import every_tile
from .tile_choice import means_all
from .tile_choice import names_tiles
from .unknown_city import UnknownCity
from .unknown_tile import UnknownTile

logger = logging.getLogger(__name__)

BuildTile = Callable[[City, Tile, TilePaths], dict]


class BuildService:
    """Chooses the tiles a request means and builds each, letting one failure spare the rest."""

    # Three collaborators: who knows the cities and their tiles, where the layout lives, and
    # the function that does one tile's work, injected so a test never reaches the network.
    def __init__(self, catalog: CityCatalog, tiles_root: Path, build_tile: BuildTile) -> None:
        self._catalog = catalog
        self._tiles_root = Path(tiles_root)
        self._build_tile = build_tile

    def targets(self, request: BuildRequest) -> list[BuildTarget]:
        """Every tile the request means, city by city in selection order."""
        if not request.build_all and request.city is None:
            raise ValueError("give a city key or ask for every city")
        if request.build_all and names_tiles(request.tiles):
            raise ValueError("named tiles apply to one city")
        records = self._catalog.records()
        keys = list(records) if request.build_all else [str(request.city)]
        targets: list[BuildTarget] = []
        for key in keys:
            city = records.get(key)
            if city is None:
                raise UnknownCity(key, "it is not a selected city")
            for tile in self._tiles_of(key, request):
                targets.append(BuildTarget(city, tile, TilePaths(self._tiles_root, city.ucdb_id, tile)))
        return targets

    def build(self, request: BuildRequest, progress: ProgressListener) -> BuildOutcome:
        """Build every target; a tile whose sources fail is recorded and the rest go on."""
        targets = self.targets(request)
        outcome = BuildOutcome(chosen=_counts(targets), totals={key: self._total(key) for key in _counts(targets)})
        progress.started("assembling bundles", len(targets), 0)
        for target in targets:
            label = f"{target.city.key} {target.tile.id}"
            progress.step_started(label, {"city": target.city.key, "tile": target.tile.id})
            started = time.time()
            try:
                provenance = self._build_tile(target.city, target.tile, target.paths)
            # One unreachable source must not abandon the remaining tiles. The failure is
            # logged with its type and never swallowed; the outcome names it.
            except Exception as error:
                logger.exception("build failed for %s after %.1fs", label, time.time() - started)
                progress.step_failed(label, str(error).splitlines()[0] if str(error) else type(error).__name__)
                outcome.failed.append(label)
                continue
            seconds = round(time.time() - started, 1)
            built = _built(target, seconds, provenance)
            outcome.built.append(built)
            progress.step_done(
                label,
                seconds,
                {
                    "city": target.city.key,
                    "tile": target.tile.id,
                    "bundle": built.bundle,
                    "several": outcome.chosen.get(target.city.key, 1) > 1,
                    "provenance": provenance,
                },
            )
        progress.finished({"built": len(outcome.built), "failed": len(outcome.failed)})
        return outcome

    def _tiles_of(self, key: str, request: BuildRequest) -> list[Tile]:
        rows = self._catalog.tile_rows(key)
        if means_all(request.tiles):
            return every_tile(rows)
        if names_tiles(request.tiles):
            return [_tile(key, part) for part in str(request.tiles).split(",") if part.strip()]
        return chosen_tiles(rows, request.densest, request.stratified)

    def _total(self, key: str) -> int:
        return len(self._catalog.tile_rows(key))


def _tile(key: str, text: str) -> Tile:
    try:
        return Tile.from_id(text.strip())
    except ValueError as exc:
        raise UnknownTile(key, text.strip()) from exc


def _counts(targets: list[BuildTarget]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for target in targets:
        counts[target.city.key] = counts.get(target.city.key, 0) + 1
    return counts


def _built(target: BuildTarget, seconds: float, provenance: dict) -> BuiltTile:
    quality = provenance.get("quality", {})
    metrics = quality.get("metrics", {})
    return BuiltTile(
        city=target.city.key,
        tile=target.tile.id,
        bundle=str(target.paths.bundle),
        seconds=seconds,
        tier=str(quality.get("tier", "?")),
        buildings=provenance.get("buildings", {}).get("count"),
        built_fraction=metrics.get("built_fraction"),
        canopy=metrics.get("canopy_gt2m"),
        population=metrics.get("population"),
        design_day=provenance.get("met", {}).get("design_day"),
        note="; ".join(quality.get("reasons") or quality.get("notes") or []),
    )
