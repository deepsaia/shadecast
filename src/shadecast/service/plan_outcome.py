"""What planning one intervention over a tile bought, with the full evaluation for the record."""

from __future__ import annotations

from pydantic import BaseModel


class PlanOutcome(BaseModel):
    city: str
    tile: str
    kind: str
    budget_usd: float
    cost_usd: float
    pixels: int
    exposure_drop: float
    people: int
    efficiency: float
    engine_seconds: float
    result: dict
