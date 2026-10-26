"""One 1 km tile as the tiles file describes it, with the stages it has reached on disk.

A tiles file written by an older build may lack an attribute or carry one under another name;
what is missing reads as zero and what is unknown is ignored, so no listing fails on history.
"""

from __future__ import annotations

from pydantic import BaseModel

from ..corpus.tile_stages import TileStages


class TileSummary(BaseModel):
    id: str
    population_2020: float = 0.0
    density_2020_per_km2: float = 0.0
    built_fraction: float = 0.0
    mean_height_m: float = 0.0
    bounds_wgs84: list[float] | None = None
    centre: list[float] | None = None
    stages: TileStages
