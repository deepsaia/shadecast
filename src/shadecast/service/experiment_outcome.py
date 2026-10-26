"""What an experiment run produced: where its rows went, how many, and the verdict its rule gave."""

from __future__ import annotations

from pydantic import BaseModel


class ExperimentOutcome(BaseModel):
    name: str
    out: str
    rows: int
    verdict: dict
