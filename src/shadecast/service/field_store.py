"""The arrays of one tile at native size, read from the files the pipeline wrote."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from ..corpus.tile_paths import TilePaths
from .met_hour import MetHour
from .missing_stage import MissingStage

DAYLIGHT_FIELD = "tmrt_daylight.npy"
HOURLY_RASTER = Path("output_folder") / "0_0" / "TMRT_0_0.tif"
RESPONSE_ARCHIVE = "response.npz"
MANIFEST = "manifest.json"
PROVENANCE = "provenance.json"
# Columns of the UMEP meteorology table the walkthrough charts.
HOUR, AIR_TEMPERATURE, SOLAR = 2, 11, 14


class FieldStore:
    """The one place that knows how a tile's fields are stored.

    Bundle rasters are GeoTIFFs, the baseline physics is a NumPy array plus the engine's hourly
    raster, and every simulated design is a compressed archive. A missing source names the stage
    that writes it and the command that runs that stage.
    """

    def __init__(self, paths: TilePaths) -> None:
        self.paths = paths

    @property
    def _paths(self) -> TilePaths:
        return self.paths

    def heights(self) -> np.ndarray:
        """Building height above ground in metres, never negative."""
        return np.maximum(self._band("Building_DSM.tif") - self._band("DEM.tif"), 0)

    def population(self) -> np.ndarray:
        return self._band("population.tif")

    def provenance(self) -> dict:
        return json.loads(self._bundle_file(PROVENANCE).read_text())

    def meteorology(self) -> list[MetHour]:
        rows = np.loadtxt(self._bundle_file("met.txt"), skiprows=1)
        return [
            MetHour(
                hour=int(row[HOUR]),
                air_c=round(float(row[AIR_TEMPERATURE]), 1),
                solar=round(float(row[SOLAR]), 0),
            )
            for row in rows
        ]

    def baseline_daylight(self) -> np.ndarray:
        """The daylight mean radiant temperature of doing nothing."""
        path = self._paths.baseline / DAYLIGHT_FIELD
        if not path.exists():
            raise MissingStage(
                "baseline", self._tile, f"sdc simulate baseline <city> --tile {self._tile}"
            )
        return np.load(path)

    def has_hourly(self) -> bool:
        return (self._paths.baseline / HOURLY_RASTER).exists()

    def hourly_temperature(self) -> np.ndarray:
        """The radiant temperature at every hour of the design day, hours first."""
        path = self._paths.baseline / HOURLY_RASTER
        if not path.exists():
            raise MissingStage(
                "baseline", self._tile, f"sdc simulate baseline <city> --tile {self._tile}"
            )
        with rasterio.open(path) as src:
            return src.read()

    def manifest(self) -> list[dict]:
        """One entry per design the engine ran, as the simulation wrote them."""
        path = self._paths.physics / MANIFEST
        if not path.exists():
            raise MissingStage(
                "physics",
                self._tile,
                f"sdc simulate treeshade <city> --tiles {self._tile}",
            )
        return json.loads(path.read_text()).get("manifest", [])

    def design_ids(self) -> list[str]:
        return [str(entry.get("id")) for entry in self.manifest()]

    def response(self, design_id: str) -> tuple[np.ndarray, np.ndarray]:
        """A design's placement mask and the cooling the engine measured for it."""
        archive = np.load(self._paths.physics / design_id / RESPONSE_ARCHIVE)
        return np.asarray(archive.get("placement")), np.asarray(archive.get("response"))

    def sources(self) -> list[Path]:
        """The files a report depends on, present or not; it is stale when any of them moves."""
        listed = [
            self._paths.bundle / PROVENANCE,
            self._paths.baseline / DAYLIGHT_FIELD,
            self._paths.physics / MANIFEST,
        ]
        if (self._paths.physics / MANIFEST).exists():
            listed.extend(
                self._paths.physics / design_id / RESPONSE_ARCHIVE
                for design_id in self.design_ids()
            )
        return listed

    @property
    def _tile(self) -> str:
        return self._paths.tile.id

    def _band(self, name: str) -> np.ndarray:
        with rasterio.open(self._bundle_file(name)) as src:
            return src.read(1)

    def _bundle_file(self, name: str) -> Path:
        path = self._paths.bundle / name
        if not path.exists():
            raise MissingStage("bundle", self._tile, f"sdc build <city> --tiles {self._tile}")
        return path
