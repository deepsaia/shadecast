"""The moves that take one legacy city into its tile, and the tile they land in."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .move import Move
from .tile_paths import TilePaths


@dataclass(frozen=True)
class Migration:
    paths: TilePaths
    moves: tuple[Move, ...]

    def __iter__(self) -> Iterator[Move]:
        return iter(self.moves)

    def __len__(self) -> int:
        return len(self.moves)
