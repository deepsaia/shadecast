"""The static layers of one tile that the surrogate conditions on.

Everything here is fixed for a tile and a design day: the bundle's geometry, land cover
and residents, the baseline temperature the engine computed for the untouched tile, the
sky view factor and sunlit fraction from that same run, and where the sun stands at noon.
Only the placement changes between plans, so a scene is loaded once and reused for every
design.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..pipeline import read_band
from . import engine_layers
from .sun import SunNoon


@dataclass(frozen=True)
class Scene:
    baseline_tmrt: np.ndarray
    building_height: np.ndarray
    canopy_height: np.ndarray
    land_cover: np.ndarray
    population: np.ndarray
    sky_view_factor: np.ndarray
    sunlit_fraction: np.ndarray
    sun: SunNoon

    @classmethod
    def load(cls, bundle: Path, surrogate_dir: Path) -> Scene:
        """Read a bundle and the baseline run beside it."""
        bundle, baseline_dir = Path(bundle), Path(surrogate_dir) / "baseline"
        provenance = json.loads((bundle / "provenance.json").read_text())
        building_dsm, _ = read_band(bundle / "Building_DSM.tif")
        terrain, _ = read_band(bundle / "DEM.tif")
        canopy, _ = read_band(bundle / "Trees.tif")
        land_cover, _ = read_band(bundle / "landcover.tif")
        population, _ = read_band(bundle / "population.tif")
        return cls(
            baseline_tmrt=np.load(baseline_dir / "tmrt_daylight.npy"),
            building_height=np.maximum(building_dsm - terrain, 0),
            canopy_height=canopy,
            land_cover=land_cover,
            population=population,
            sky_view_factor=engine_layers.sky_view_factor(baseline_dir),
            sunlit_fraction=engine_layers.sunlit_fraction(baseline_dir),
            sun=SunNoon.for_day(provenance["aoi"]["lat"], provenance["met"]["design_day"]),
        )
