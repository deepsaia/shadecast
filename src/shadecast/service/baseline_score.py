"""What doing nothing costs the tile: weighted exposure and the people above the threshold."""

from __future__ import annotations

from pydantic import BaseModel


class BaselineScore(BaseModel):
    exposure: float
    at_risk: int
