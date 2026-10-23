"""What an assessment compares: a trained model, the designs it never saw, and their tile."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AssessmentInputs:
    model_dir: Path  # holds model.pt, training_report.json and manifest.json
    surrogate_dir: Path  # holds the generated responses and the baseline
    bundle: Path
    only: list[str] | None = None  # designs to assess instead of the held-out set
