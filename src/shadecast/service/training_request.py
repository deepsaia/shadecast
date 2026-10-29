"""What one training run is asked to do: which tiles or pairs, the holdout, the patches."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from pydantic import Field


class TrainingRequest(BaseModel):
    target: str | None = None  # a city key, or a surrogate directory when ``bundle`` is given
    bundle: Path | None = None
    pair: list[str] = Field(default_factory=list)  # city keys or SURROGATE=BUNDLE, pooled
    tiles: str | None = None  # tile ids separated by commas; None means every tile with physics
    holdout_city: str | None = None
    epochs: int = 60
    patch: int = 256
    per_entry: int = 24
    channels: str = "engine"
    densest: int | None = None
    stratified: int | None = None
    resume: bool = False
