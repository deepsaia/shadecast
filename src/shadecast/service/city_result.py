"""One tile's part of the cross-city results: its facts, its plans and its matched pair."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .baseline_score import BaselineScore
from .matched_pair import MatchedPair
from .physics_facts import PhysicsFacts
from .plan import Plan
from .tile_facts import TileFacts


class CityResult(BaseModel):
    key: str
    name: str
    tile: str
    facts: TileFacts
    baseline: BaselineScore | None
    plans: list[Plan] = Field(default_factory=list)
    physics: PhysicsFacts | None
    matched: MatchedPair | None
