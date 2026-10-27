"""Count how many of an urban centre's tiles have reached each stage."""

from __future__ import annotations

from ..corpus.tile_stages import TileStages
from .stage_counts import StageCounts


def count_stages(reached: list[TileStages], tiles: int) -> StageCounts:
    """How many of the centre's ``tiles`` reached each stage, from the stages of those on disk.

    The denominator comes from the centre's record, a City for a selected city and an UrbanCentre
    for any other, so the caller supplies it rather than this function knowing both record types.
    """
    return StageCounts(
        tiles=tiles,
        bundle=sum(stages.bundle for stages in reached),
        baseline=sum(stages.baseline for stages in reached),
        physics=sum(stages.physics for stages in reached),
        model=sum(stages.model for stages in reached),
        results=sum(stages.results for stages in reached),
    )
