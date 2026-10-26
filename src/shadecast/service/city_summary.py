"""One selected city as a command or client sees it: its strata and what its tiles have reached."""

from __future__ import annotations

from pydantic import BaseModel

from .stage_counts import StageCounts


class CitySummary(BaseModel):
    key: str
    ucdb_id: int
    name: str
    country: str
    region: str
    koppen: str | None
    income: str | None
    population_2025: int
    in_wri: bool
    stages: StageCounts
