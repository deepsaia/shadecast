"""One tile's place in the ranking by cooling per dollar of its scattered plans."""

from __future__ import annotations

from pydantic import BaseModel


class RankingRow(BaseModel):
    key: str
    name: str
    scattered_per_1k: float | None
    clustered_per_1k: float | None
    gain: float | None
    canopy: float | None
    built_fraction: float | None
