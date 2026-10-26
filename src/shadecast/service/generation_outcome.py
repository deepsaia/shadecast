"""What one tile's generation left behind: where, how many designs, how long."""

from __future__ import annotations

from pydantic import BaseModel


class GenerationOutcome(BaseModel):
    tile: str
    destination: str
    entries: int
    seconds: float
