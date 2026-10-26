"""One tile a build will assemble: the city record, the square, and where the layout puts it."""

from __future__ import annotations

from dataclasses import dataclass

from ..cities import City
from ..corpus.tile import Tile
from ..corpus.tile_paths import TilePaths


@dataclass(frozen=True)
class BuildTarget:
    city: City
    tile: Tile
    paths: TilePaths
