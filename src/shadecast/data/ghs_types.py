"""Type aliases for the GHS Mollweide grid."""

from __future__ import annotations

# A box in Mollweide metres: west, south, east, north.
Bounds = tuple[float, float, float, float]
# Row and column of a 1,000 km GHS tile, as the published file names count them.
TileRC = tuple[int, int]
