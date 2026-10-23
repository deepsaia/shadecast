"""Backfill layers and provenance that a bundle predates.

Bundles built by an older version of the builder can be missing layers that were added later,
or provenance fields such as the urban centre and the citation of each layer. Rebuilding is not
always an option: once physics has been run against a bundle's geometry, every generated
response is tied to that exact grid, and a rebuild that shifts the study area silently
invalidates hours of simulation.

So missing layers are recomputed onto the bundle's own recorded grid instead, and missing
provenance is filled in from the selection and the registry without touching a raster.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import rasterio

from .aoi import AOI
from .build import LAYER_SOURCES, source_record, urban_centre_record
from .cities import City
from .data import population as population_layer
from .data.landcover import to_umep

logger = logging.getLogger(__name__)


def aoi_from_provenance(bundle: Path) -> AOI:
    """Reconstruct the exact grid a bundle was built on."""
    provenance = json.loads((Path(bundle) / "provenance.json").read_text())
    record = provenance["aoi"]
    # Older bundles carried the city name inside the aoi block; newer ones keep it
    # in a separate city block. Fall back to the directory name.
    name = record.get("name") or provenance.get("city", {}).get("key") or Path(bundle).name
    return AOI(name, record["lat"], record["lon"], side_m=record["side_m"], res_m=record["res_m"])


def _write_like(bundle: Path, name: str, array: np.ndarray, dtype: str) -> Path:
    """Write a layer using an existing layer's georeferencing, so grids cannot drift."""
    with rasterio.open(Path(bundle) / "DEM.tif") as reference:
        profile = reference.profile
    profile.update(dtype=dtype, count=1, compress="deflate", tiled=True)
    target = Path(bundle) / name
    with rasterio.open(target, "w", **profile) as destination:
        destination.write(array.astype(dtype), 1)
    return target


def building_height(bundle: Path) -> np.ndarray:
    with rasterio.open(Path(bundle) / "Building_DSM.tif") as src:
        surface = src.read(1)
    with rasterio.open(Path(bundle) / "DEM.tif") as src:
        terrain = src.read(1)
    return np.maximum(surface - terrain, 0)


def backfill_provenance(bundle: Path, city: City) -> list[str]:
    """Add the urban centre and the citation of each layer to an older provenance file.

    Returns the sections touched, so a caller can say exactly what changed and a second
    call on the same bundle returns nothing.
    """
    path = Path(bundle) / "provenance.json"
    provenance = json.loads(path.read_text())
    touched: list[str] = []
    if "urban_centre" not in provenance:
        provenance["urban_centre"] = urban_centre_record(city)
        touched.append("urban_centre")
    for layer, key in LAYER_SOURCES.items():
        section = provenance.get(layer)
        if isinstance(section, dict) and "source_key" not in section:
            section.update(source_record(key))
            touched.append(layer)
    if touched:
        path.write_text(json.dumps(provenance, indent=2))
        logger.info("%s: provenance gained %s", Path(bundle).name, ", ".join(touched))
    return touched


def backfill(bundle: Path) -> list[str]:
    """Add any missing layers to a bundle. Returns what was written."""
    bundle = Path(bundle)
    written: list[str] = []
    heights = building_height(bundle)

    if not (bundle / "population.tif").exists():
        aoi = aoi_from_provenance(bundle)
        logger.info("%s: backfilling population on its recorded grid", bundle.name)
        _write_like(bundle, "population.tif", population_layer.dasymetric(aoi, heights), "float32")
        written.append("population.tif")

    if not (bundle / "landcover_umep.tif").exists() and (bundle / "landcover.tif").exists():
        with rasterio.open(bundle / "landcover.tif") as src:
            cover = src.read(1)
        _write_like(bundle, "landcover_umep.tif", to_umep(cover, heights), "float32")
        written.append("landcover_umep.tif")

    return written
