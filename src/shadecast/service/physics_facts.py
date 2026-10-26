"""How many designs the engine ran for a tile and how long each took."""

from __future__ import annotations

from pydantic import BaseModel


class PhysicsFacts(BaseModel):
    designs: int
    engine_minutes: float
    seconds_per_design_min: int
    seconds_per_design_max: int
