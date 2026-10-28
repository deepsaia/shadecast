"""What a manifest is built from: the trained pairs, the training report, and the weights."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ManifestInputs:
    model_id: str
    created: str  # ISO 8601
    pairs: list[tuple[Path, Path]]  # (physics directory, bundle) per tile trained on
    report: dict  # what train() returned
    patch_px: int
    per_entry: int  # patches cropped per design
    model_path: Path
