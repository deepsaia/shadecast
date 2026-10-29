"""The outcome curves of one tile: the surrogate over every coverage in every arrangement, for one model."""

from __future__ import annotations

from pydantic import BaseModel

from .sweep_curve import SweepCurve
from .sweep_design import SweepDesign


class Sweep(BaseModel):
    model_id: str
    created: str
    coverages: list[float]  # shares of the plantable ground
    thresholds: list[float]  # degrees C the threshold-bound outcomes are kept at
    curves: list[SweepCurve]
    designs: list[SweepDesign]
    seconds: float  # the surrogate time it took to compute
    fresh: bool = True  # computed by this call, rather than read back from disk
