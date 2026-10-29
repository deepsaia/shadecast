"""What a build left behind: the bundles built, the tiles that failed, and the counts chosen."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field

from .built_tile import BuiltTile


class BuildOutcome(BaseModel):
    built: list[BuiltTile] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    chosen: dict[str, int] = Field(default_factory=dict)  # tiles chosen per city key
    totals: dict[str, int] = Field(default_factory=dict)  # tiles the city has, per key
