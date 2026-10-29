"""One placement's price-free outcomes against doing nothing; the threshold-bound two at every threshold."""

from __future__ import annotations

from pydantic import BaseModel


class SweepPoint(BaseModel):
    exposure_drop: float
    equity_gap_change: float
    excess_removed: list[float]  # one per threshold of the sweep
    people: list[float]  # one per threshold of the sweep
