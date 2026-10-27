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

    def with_model(self, found: bool) -> TileStages:
        """These stages with the model flag as the models root answers it; no tile proves it."""
        return self.model_copy(update={"model": found})
