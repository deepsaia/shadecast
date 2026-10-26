"""How many tiles see scattered beat clustered per dollar at matched coverage, and by how much."""

from __future__ import annotations

from pydantic import BaseModel


class ArrangementVerdict(BaseModel):
    ratios: dict[str, float]
    cities_compared: int
    scattered_wins: int
    ratio_min: float | None
    ratio_max: float | None
