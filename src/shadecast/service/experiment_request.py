"""Which pre-registered experiment to run, over which cities, with which budget, written where."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ExperimentRequest(BaseModel):
    name: str  # factorial, targeting or channel
    cities: list[str] = Field(default_factory=list)
    out: Path | None = None  # default: <data root>/<name>.json
    budget: float = 2_288_000.0
