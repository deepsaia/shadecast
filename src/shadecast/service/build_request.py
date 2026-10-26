"""What one build is asked to do: which city or every city, and which of its tiles."""

from __future__ import annotations

from pydantic import BaseModel


class BuildRequest(BaseModel):
    city: str | None = None
    build_all: bool = False
    tiles: str | None = None  # None: the densest tile; ids separated by commas; "all" or ""
    densest: int | None = None
    stratified: int | None = None
