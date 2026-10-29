"""What a person asks the simulator: a tile and the levers, with one of coverage or budget set."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import model_validator


class Scenario(BaseModel):
    target: str
    tile: str | None = None
    kind: str = "tree"
    arrangement: str = "clustered"
    coverage: float | None = None  # share of the feasible ground planted, above 0 and at most 1
    budget_usd: float | None = None
    unit_cost: float | None = None  # USD per square metre; the catalogue's price when not given
    maintenance: float | None = None  # annual maintenance as a share of capital; the catalogue's when not given

    @model_validator(mode="after")
    def one_lever_sets_the_size(self) -> Scenario:
        if (self.coverage is None) == (self.budget_usd is None):
            raise ValueError("give exactly one of coverage and budget_usd")
        if self.coverage is not None and not 0.0 < self.coverage <= 1.0:
            raise ValueError("coverage is a share of the feasible ground, above 0 and at most 1")
        if self.budget_usd is not None and self.budget_usd <= 0.0:
            raise ValueError("budget_usd must be above 0")
        if self.unit_cost is not None and self.unit_cost <= 0.0:
            raise ValueError("unit_cost is USD per square metre, above 0")
        if self.maintenance is not None and not 0.0 <= self.maintenance < 1.0:
            raise ValueError("maintenance is a yearly share of capital, from 0 up to but not including 1")
        return self
