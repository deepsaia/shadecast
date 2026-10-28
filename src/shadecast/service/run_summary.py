"""One run in progress: a simulation holding its lock or a training that left a checkpoint."""

from __future__ import annotations

from pydantic import BaseModel


class RunSummary(BaseModel):
    kind: str
    city: str
    tile: str | None
    model: str | None
    started: str
    alive: bool | None  # None when the run leaves no process id behind, as training does
    designs_done: int | None
    designs_planned: int | None
