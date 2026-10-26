"""The tiles ranked by cooling per dollar, and the spread from top to bottom."""

from __future__ import annotations

from pydantic import BaseModel

from .ranking_row import RankingRow


class Ranking(BaseModel):
    rows: list[RankingRow]
    spread: float | None
