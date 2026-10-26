"""Which stages a tile has reached, read from the files that prove each one."""

from __future__ import annotations

from pydantic import BaseModel

STAGE_NAMES = ("bundle", "baseline", "physics", "model", "results")


class TileStages(BaseModel):
    """One flag per stage of the pipeline, in the order the pipeline runs them."""

    bundle: bool = False
    baseline: bool = False
    physics: bool = False
    model: bool = False
    results: bool = False
