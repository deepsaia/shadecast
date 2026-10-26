"""Raised when the tile id a command named is not a tile id at all."""

from __future__ import annotations


class UnknownTile(LookupError):
    def __init__(self, centre: str, tile_id: str) -> None:
        super().__init__(
            f"{centre}: {tile_id!r} is not a tile id of the form t<zone>_<e_km>_<n_km>"
        )
        self.tile_id = tile_id
