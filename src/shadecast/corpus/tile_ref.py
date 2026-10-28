"""``<urban centre id>/<tile id>``: how a manifest names a tile, its path under the tiles root.

A reference is text, so a manifest stays readable and small, and it is the same text whether the
model learned from one tile or from many. The two halves are read back here, in one place.
"""

from __future__ import annotations

SEPARATOR = "/"


def ref_of(urban_centre: int, tile_id: str) -> str:
    return f"{urban_centre}{SEPARATOR}{tile_id}"


def centre_of(ref: str) -> int:
    """The urban centre id in front of the slash."""
    head, _ = _halves(ref)
    return int(head)


def tile_of(ref: str) -> str:
    """The tile id after the slash."""
    _, tail = _halves(ref)
    return tail


def _halves(ref: str) -> tuple[str, str]:
    head, separator, tail = str(ref).partition(SEPARATOR)
    if not separator or not head.isdigit() or not tail:
        raise ValueError(
            f"{ref!r} is not a tile reference <urban centre id>/<tile id>; "
            "a manifest written before the lean layout needs migrating"
        )
    return head, tail
