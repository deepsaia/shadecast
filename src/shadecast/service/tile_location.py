"""Where everything for one tile lives, as text paths, and which stages have run."""

from __future__ import annotations

from pydantic import BaseModel

from ..corpus.tile_stages import TileStages


class TileLocation(BaseModel):
    urban_centre: int
    tile: str
    root: str
    bundle: str
    baseline: str
    surrogate: str
    plans: str
    results: str
    stages: TileStages
