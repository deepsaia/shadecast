"""A rectangular read of a 100 m GHS raster, kept in the grid's own coordinates.

Per-tile statistics are sums over the cells whose centres fall inside a tile's footprint. The
footprint arrives as a polygon in the grid's coordinates, so the window rasterises it onto its
own cells and reads through the mask, with no reprojection of the raster itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from shapely.geometry.base import BaseGeometry

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

    @property
    def transform(self) -> Affine:
        return Affine(ghs_grid.CELL_M, 0.0, self.origin[0], 0.0, -ghs_grid.CELL_M, self.origin[1])

    def mask(self, footprint: BaseGeometry) -> np.ndarray:
        """True for the cells whose centres lie inside a footprint given in grid coordinates."""
        burned = rasterize(
            [(footprint, 1)],
            out_shape=self.values.shape,
            transform=self.transform,
            fill=0,
            dtype="uint8",
        )
        return burned.astype(bool)

    def inside(self, footprint: BaseGeometry) -> np.ndarray:
        return self.values[self.mask(footprint)]

    def sum_inside(self, footprint: BaseGeometry) -> float:
        return float(self.inside(footprint).sum())

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
        row = round((self.origin[1] - clip[3]) / ghs_grid.CELL_M)
        col = round((clip[0] - self.origin[0]) / ghs_grid.CELL_M)
        self.values[row : row + data.shape[0], col : col + data.shape[1]] = data
        return int(data.size)
