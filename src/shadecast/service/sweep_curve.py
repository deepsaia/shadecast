"""One arrangement's outcomes along the coverage ladder of a sweep."""

from __future__ import annotations

from pydantic import BaseModel

from .sweep_point import SweepPoint


class SweepCurve(BaseModel):
    arrangement: str
    points: list[SweepPoint]  # one per coverage of the sweep
