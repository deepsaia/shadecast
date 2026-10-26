"""The measured results across every tile with physics, as the results page draws them."""

from __future__ import annotations

from pydantic import BaseModel

from .arrangement_verdict import ArrangementVerdict
from .city_result import CityResult
from .ranking import Ranking
from .results_totals import ResultsTotals


class Results(BaseModel):
    threshold_C: float
    as_of: str
    cities: list[CityResult]
    totals: ResultsTotals
    arrangement: ArrangementVerdict
    ranking: Ranking
    factorial: list[dict] | dict | None
    targeting: list[dict] | dict | None
    channel: list[dict] | dict | None
