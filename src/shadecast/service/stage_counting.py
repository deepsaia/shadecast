"""Count how many tile directories of an urban centre prove each stage."""

from __future__ import annotations

from pathlib import Path

from ..corpus.tile_paths import TilePaths
from .stage_counts import StageCounts


# Three arguments: where to look, which centre, and the denominator its record gives. The
# record is a City for a selected city and an UrbanCentre for any other centre, so the caller
# supplies the tile count rather than this function knowing both record types.
def count_stages(tiles_root: Path, urban_centre: int, tiles: int) -> StageCounts:
    """How many tiles of the centre have reached each stage, out of the ``tiles`` it has."""
    reached = [paths.stages() for paths in TilePaths.existing(tiles_root, urban_centre)]
    return StageCounts(
        tiles=tiles,
        bundle=sum(stages.bundle for stages in reached),
        baseline=sum(stages.baseline for stages in reached),
        physics=sum(stages.physics for stages in reached),
        model=sum(stages.model for stages in reached),
        results=sum(stages.results for stages in reached),
    )
