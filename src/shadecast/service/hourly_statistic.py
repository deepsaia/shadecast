"""The median and maximum of the radiant temperature field at one hour of the design day."""

from __future__ import annotations

from pydantic import BaseModel


class HourlyStatistic(BaseModel):
    hour: int
    median: float
    max: float
