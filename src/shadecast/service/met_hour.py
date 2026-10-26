"""One hour of the design day's meteorology as the walkthrough charts it."""

from __future__ import annotations

from pydantic import BaseModel


class MetHour(BaseModel):
    hour: int
    air_c: float
    solar: float
