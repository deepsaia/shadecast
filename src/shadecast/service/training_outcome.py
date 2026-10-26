"""What a training run left behind and how it went, with the full report for the record."""

from __future__ import annotations

from pydantic import BaseModel


class TrainingOutcome(BaseModel):
    model_id: str
    destination: str
    resumed: bool
    patches: int
    designs: int
    cities: int
    skill: float
    mae_c: float
    zero_mae_c: float
    beats_nothing: bool
    holdout_mode: str
    best_epoch: int
    last_epoch: int
    interrupted: bool
    report: dict
