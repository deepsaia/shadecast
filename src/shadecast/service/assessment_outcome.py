"""How a model fared against engine truth, and where the full report was written."""

from __future__ import annotations

from pydantic import BaseModel


class AssessmentOutcome(BaseModel):
    model_dir: str
    report_path: str
    skill: float
    beats_nothing: bool
    error: float
    spearman: float | None
    speedup: float | None
    report: dict
