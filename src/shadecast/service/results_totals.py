"""How much the results rest on: tiles, plans and the range of budgets."""

from __future__ import annotations

from pydantic import BaseModel


class ResultsTotals(BaseModel):
    cities: int
    plans: int
    budget_min_m: float | None
    budget_max_m: float | None
