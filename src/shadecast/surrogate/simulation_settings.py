"""Everything one simulation run is told, in one object, so callers pass one thing."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class SimulationSettings:
    plan: list[dict] | None = None  # None means the default plan
    kind: str = "tree"
    jobs: int = 1  # engine runs side by side; the baseline always runs alone first
    engine_threads: int | None = field(default=None)  # None lets the engine pick

    def __post_init__(self) -> None:
        if self.jobs < 1:
            raise ValueError("jobs must be at least 1")
