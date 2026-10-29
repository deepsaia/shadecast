"""Everything a tile can say about itself: its facts always, then whatever stages it has reached."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field

from ..corpus.tile_stages import TileStages
from .baseline_score import BaselineScore
from .hourly_statistic import HourlyStatistic
from .met_hour import MetHour
from .physics_facts import PhysicsFacts
from .plan import Plan
from .tile_facts import TileFacts


class TileReport(BaseModel):
    city: str
    tile: str
    name: str
    stages: TileStages
    facts: TileFacts
    baseline: BaselineScore | None = None
    met: list[MetHour] = Field(default_factory=list)
    hourly: list[HourlyStatistic] = Field(default_factory=list)
    plans: list[Plan] = Field(default_factory=list)
    physics: PhysicsFacts | None = None
