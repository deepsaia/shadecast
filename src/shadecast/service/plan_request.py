"""What one plan is asked for: a tile, an intervention kind and a budget."""

from __future__ import annotations

from pydantic import BaseModel


class PlanRequest(BaseModel):
    target: str
    tile: str | None = None
    kind: str = "tree"
    budget_usd: float = 10_000_000.0
