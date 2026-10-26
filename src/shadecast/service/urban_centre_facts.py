"""The strata of the urban centre a tile belongs to, as the bundle recorded them."""

from __future__ import annotations

from pydantic import BaseModel


class UrbanCentreFacts(BaseModel):
    id: int | None = None
    name: str | None = None
    koppen: str | None = None
    income: str | None = None
    population_2025: int | None = None
    tiles: int | None = None
