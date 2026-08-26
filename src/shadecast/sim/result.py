"""Outcome of a single physics engine run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunResult:
    """Where a run wrote its output and what it cost."""

    base_path: Path
    seconds: float
    tmrt_path: Path
    returncode: int

    def as_dict(self) -> dict[str, object]:
        return {
            "base_path": str(self.base_path),
            "seconds": round(self.seconds, 1),
            "tmrt": str(self.tmrt_path),
            "returncode": self.returncode,
        }
