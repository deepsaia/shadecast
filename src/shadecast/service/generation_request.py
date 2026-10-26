"""What one generation is asked to do: which city, which of its tiles, how many engines at once."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class GenerationRequest(BaseModel):
    target: str
    tiles: str | None = None  # None: the densest built tile; ids separated by commas; "all" or ""
    out: Path | None = None  # where to write, for one tile; else beside the bundle
    jobs: int = 1
    kind: str = "tree"
