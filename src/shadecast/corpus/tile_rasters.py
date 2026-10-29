"""The three rasters a tile is described from, read once over an urban centre."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..data.built import GHS_BUILT_H
from ..data.built import GHS_BUILT_S
from ..data.ghs_product import CACHE_ROOT
from ..data.ghs_product import read_window
from ..data.ghs_types import Bounds
from ..data.population import GHS_POP
from ..data.raster_window import RasterWindow


@dataclass(frozen=True)
class TileRasters:
    """Population, built surface and building height over one box, on the same grid."""

    population_2020: RasterWindow
    built_surface: RasterWindow
    building_height: RasterWindow

    @classmethod
    def read(cls, bounds: Bounds, cache_root: Path = CACHE_ROOT) -> TileRasters:
        return cls(
            population_2020=read_window(GHS_POP, bounds, cache_root),
            built_surface=read_window(GHS_BUILT_S, bounds, cache_root),
            building_height=read_window(GHS_BUILT_H, bounds, cache_root),
        )
