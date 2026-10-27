"""One trained surrogate model as the catalog lists it: where, when, and what it learned."""

from __future__ import annotations

from pydantic import BaseModel


class ModelSummary(BaseModel):
    id: str
    urban_centres: list[int]
    created: str
    channel: str
    tile: str | None
    path: str
    has_weights: bool
    has_manifest: bool
    skill: float | None
    tiles_trained: int
    manifest: dict
