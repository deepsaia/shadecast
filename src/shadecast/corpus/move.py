"""One directory move in a migration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Move:
    source: Path
    target: Path
    label: str  # what the directory is: bundle or surrogate
