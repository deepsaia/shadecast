"""An engine-verified design placed on the sweep's axes: its arrangement, coverage and outcomes."""

from __future__ import annotations

from pydantic import BaseModel

from .sweep_point import SweepPoint


class SweepDesign(BaseModel):
    id: str
    arrangement: str
    coverage: float  # share of the plantable ground, the sweep's axis
    point: SweepPoint
