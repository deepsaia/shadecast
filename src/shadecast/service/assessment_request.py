"""Which model to judge, on which tile, against which designs."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class AssessmentRequest(BaseModel):
    target: str  # a city key, or a model directory when ``physics_dir`` and ``bundle`` are given
    physics_dir: Path | None = None
    bundle: Path | None = None
    model: str | None = None  # a model id of the city, else its newest model
    tile: str | None = None  # the tile to judge on, else the densest with physics
    design: list[str] | None = None  # designs to assess instead of the held-out set
