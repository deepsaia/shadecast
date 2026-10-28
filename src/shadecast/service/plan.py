"""One simulated design scored as a plan: what it covers, what it costs and what it buys."""

from __future__ import annotations

from pydantic import BaseModel


class Plan(BaseModel):
    id: str
    arrangement: str
    coverage: float
    trees: int
    cost_usd: float
    cost_m: float
    exposure_drop: float
    people: int
    efficiency: float
