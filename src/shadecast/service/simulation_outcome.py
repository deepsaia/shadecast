"""What one tile's simulation left behind: where, how many designs, how long."""

from __future__ import annotations

from pydantic import BaseModel


class SimulationOutcome(BaseModel):
    tile: str
    destination: str
    entries: int
    seconds: float
