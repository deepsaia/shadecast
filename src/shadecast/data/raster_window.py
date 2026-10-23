"""A rectangular read of a 100 m GHS raster, kept in the grid's own coordinates.

Per-tile statistics over an urban centre are sums and means over blocks of 100 m cells. Keeping
the read in Mollweide metres, with its north-west corner recorded, makes every block a plain
slice and every tile total exact, with no reprojection anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

from . import ghs_grid
from .ghs_types import Bounds


@dataclass(frozen=True)
class RasterWindow:
    """100 m cell values over a box, rows running south from `origin`, columns running east."""

    values: np.ndarray
    origin: tuple[float, float]  # x of the west edge, y of the north edge

    @classmethod
    def zeros(cls, bounds: Bounds) -> RasterWindow:
        """An empty window over a box already snapped to whole cells."""
        minx, miny, maxx, maxy = bounds
        shape = (round((maxy - miny) / ghs_grid.CELL_M), round((maxx - minx) / ghs_grid.CELL_M))
        return cls(np.zeros(shape, dtype="float32"), (minx, maxy))

    def _offsets(self, bounds: Bounds) -> tuple[int, int]:
        """Row and column of the north-west cell of a box inside this window."""
        minx, _, _, maxy = bounds
        row = round((self.origin[1] - maxy) / ghs_grid.CELL_M)
        col = round((minx - self.origin[0]) / ghs_grid.CELL_M)
        return row, col

    def block(self, bounds: Bounds) -> np.ndarray:
        """The cells inside a box, clipped to the window."""
        minx, miny, maxx, maxy = bounds
        row, col = self._offsets(bounds)
        rows = round((maxy - miny) / ghs_grid.CELL_M)
        cols = round((maxx - minx) / ghs_grid.CELL_M)
        return self.values[max(row, 0) : max(row + rows, 0), max(col, 0) : max(col + cols, 0)]

    def sum_in(self, bounds: Bounds) -> float:
        return float(self.block(bounds).sum())

    def mean_in(self, bounds: Bounds) -> float:
        block = self.block(bounds)
        return float(block.mean()) if block.size else 0.0

    def paste(self, tile_path: Path, bounds: Bounds, nodata: float | None) -> int:
        """Read the part of one tile raster inside the box into this window.

        Three arguments because a read has three facts that are not the window's own: which
        file, which clip box, and what value the product uses for missing. Returns cells read.
        """
        with rasterio.open(tile_path) as src:
            tile = src.bounds
            clip = (
                max(bounds[0], tile.left),
                max(bounds[1], tile.bottom),
                min(bounds[2], tile.right),
                min(bounds[3], tile.top),
            )
            if clip[0] >= clip[2] or clip[1] >= clip[3]:
                return 0
            window = from_bounds(*clip, transform=src.transform)
            data = src.read(1, window=window).astype("float32")
            fill = src.nodata if nodata is None else nodata
        if fill is not None:
            data[data == fill] = 0.0
        data[data < 0] = 0.0
        row, col = self._offsets(clip)
        self.values[row : row + data.shape[0], col : col + data.shape[1]] = data
        return int(data.size)
