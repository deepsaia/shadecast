"""What running a tile's baseline left behind: where, which day, whether it was already there."""

from __future__ import annotations

from pydantic import BaseModel


class BaselineOutcome(BaseModel):
    tile: str
    design_day: str
    destination: str
    seconds: float | None  # None when the field was already on disk and the engine did not run
    kept: bool
