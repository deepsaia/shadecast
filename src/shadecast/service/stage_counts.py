"""How many of a city's tiles have reached each stage, out of how many tiles it has."""

from __future__ import annotations

from pydantic import BaseModel


class StageCounts(BaseModel):
    tiles: int
    bundle: int = 0
    baseline: int = 0
    physics: int = 0
    model: int = 0
    results: int = 0
