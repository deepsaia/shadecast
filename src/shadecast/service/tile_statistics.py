"""Statistics over one urban centre's tiles: counts, people, spreads and how far each stage got."""

from __future__ import annotations

from pydantic import BaseModel

from .stage_counts import StageCounts


class TileStatistics(BaseModel):
    urban_centre: int
    name: str
    population_2025: int
    area_km2: float
    tiles: int
    populated_tiles: int
    population_2020: float
    tiles_over: dict[str, int]
    quantiles: dict[str, dict[str, float]]
    stages: StageCounts
