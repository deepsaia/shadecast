"""Which of a centre's tiles a request means, from the described rows: one, all, or a selection."""

from __future__ import annotations

from ..corpus.tile import Tile
from ..corpus.tiling import select_densest
from ..corpus.tiling import select_stratified

ALL = "all"


def means_all(tiles: str | None) -> bool:
    return tiles is not None and tiles.strip().lower() in ("", ALL)


def names_tiles(tiles: str | None) -> bool:
    return tiles is not None and not means_all(tiles)


def chosen_tiles(rows: list[dict], densest: int | None, stratified: int | None) -> list[Tile]:
    """The densest tile, or the K densest, or K spread over built-fraction terciles.

    Three arguments: the described rows and the two selection sizes, of which at most one is
    set; named ids are resolved by the caller, which knows the city for the error message.
    """
    if densest:
        picked = select_densest(rows, densest)
    elif stratified:
        picked = select_stratified(rows, stratified)
    else:
        picked = select_densest(rows, 1)
    if not picked:
        raise ValueError("the centre has no tiles to build")
    return [Tile.from_id(str(row.get("id"))) for row in picked]


def every_tile(rows: list[dict]) -> list[Tile]:
    return [Tile.from_id(str(row.get("id"))) for row in rows]
