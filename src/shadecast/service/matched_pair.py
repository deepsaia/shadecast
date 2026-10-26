"""The clustered and scattered plans of one tile closest in coverage, and their efficiency ratio."""

from __future__ import annotations

from pydantic import BaseModel

from .plan import Plan


class MatchedPair(BaseModel):
    clustered: Plan
    scattered: Plan
    ratio: float | None
