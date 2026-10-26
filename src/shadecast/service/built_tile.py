"""One bundle a build produced, with the facts its provenance records."""

from __future__ import annotations

from pydantic import BaseModel


class BuiltTile(BaseModel):
    city: str
    tile: str
    bundle: str
    seconds: float
    tier: str
    buildings: int | None
    built_fraction: float | None
    canopy: float | None
    population: float | None
    design_day: str | None
    note: str
