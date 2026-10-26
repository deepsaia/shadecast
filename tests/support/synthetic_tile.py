"""A small tile on disk with every file the pipeline writes, so services run without the engine.

Sixteen by sixteen metres: a block of buildings in one corner, two people on every pixel, a hot
baseline, three designs of known arrangements and one sparse probe. Every number is chosen so a
test can predict the answer.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

SIZE = 16
URBAN_CENTRE = 6143
TILE_ID = "t43N_249_2547"
DESIGN_DAY = "2025-05-20"
BASELINE_C = 50.0
ENGINE_SECONDS = (300.0, 360.0, 330.0, 90.0)
PLAN_IDS = ("clustered_0101", "random_uniform_0201", "corridor_0302")
PROBE_ID = "sparse_probe_0000"


def write_bundle(root: Path) -> Path:
    """The bundle of the tile: three rasters, meteorology and provenance. Returns the tile root."""
    tile = Path(root) / str(URBAN_CENTRE) / TILE_ID
    bundle = tile / "bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    dem = np.full((SIZE, SIZE), 100.0, dtype="float32")
    _write_raster(bundle / "DEM.tif", dem)
    _write_raster(bundle / "Building_DSM.tif", dem + heights())
    _write_raster(bundle / "population.tif", np.full((SIZE, SIZE), 2.0, dtype="float32"))
    (bundle / "met.txt").write_text(_met_text())
    (bundle / "provenance.json").write_text(json.dumps(provenance()))
    return tile


def write_baseline(tile: Path) -> Path:
    """The baseline physics: the daylight mean field and the 24 band hourly raster."""
    baseline = Path(tile) / "surrogate" / "baseline"
    baseline.mkdir(parents=True, exist_ok=True)
    np.save(baseline / "tmrt_daylight.npy", np.full((SIZE, SIZE), BASELINE_C, dtype="float32"))
    hours = np.stack([np.full((SIZE, SIZE), 30.0 + hour, dtype="float32") for hour in range(24)])
    out = baseline / "output_folder" / "0_0"
    out.mkdir(parents=True, exist_ok=True)
    _write_raster(out / "TMRT_0_0.tif", hours)
    return baseline


def write_designs(tile: Path) -> Path:
    """Three plans and one probe, each with its archive, and the manifest that lists them."""
    surrogate = Path(tile) / "surrogate"
    entries = []
    for design_id, seconds in zip((*PLAN_IDS, PROBE_ID), ENGINE_SECONDS, strict=True):
        placement, response = design(design_id)
        folder = surrogate / design_id
        folder.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(folder / "response.npz", placement=placement, response=response)
        entry = {
            "id": design_id,
            "family": design_id.rsplit("_", 1)[0],
            "kind": "tree",
            "design_day": DESIGN_DAY,
            "placed_px": int(placement.sum()),
            "coverage": float(placement.mean()),
            "engine_seconds": seconds,
        }
        (folder / "meta.json").write_text(json.dumps(entry))
        entries.append(entry)
    manifest = {
        "kind": "tree",
        "entries": len(entries),
        "design_day": DESIGN_DAY,
        "manifest": entries,
    }
    (surrogate / "manifest.json").write_text(json.dumps(manifest))
    return surrogate


def heights() -> np.ndarray:
    """Buildings ten metres tall in the top left quarter, ground everywhere else."""
    field = np.zeros((SIZE, SIZE), dtype="float32")
    field[:8, :8] = 10.0
    return field


def design(design_id: str) -> tuple[np.ndarray, np.ndarray]:
    """Placement and cooling for one design id, all on open ground."""
    placement = np.zeros((SIZE, SIZE), dtype=bool)
    response = np.zeros((SIZE, SIZE), dtype="float32")
    if design_id == "clustered_0101":
        placement[10:14, 10:14] = True
        response[placement] = 1.0
    elif design_id == "random_uniform_0201":
        placement[9, 1], placement[11, 5], placement[13, 9], placement[15, 13] = (
            True,
            True,
            True,
            True,
        )
        placement[1, 9], placement[3, 11], placement[5, 13], placement[7, 15] = (
            True,
            True,
            True,
            True,
        )
        response[placement] = 1.5
    elif design_id == "corridor_0302":
        placement[8, 0:4] = True
    else:
        placement[15, 15] = True
        response[placement] = 0.1
    return placement, response


def provenance() -> dict:
    return {
        "city": {"key": "ahmedabad", "name": "Ahmedabad"},
        "met": {"design_day": DESIGN_DAY, "source": "Open-Meteo ERA5 archive"},
        "quality": {"tier": "A"},
        "buildings": {"count": 1, "built_fraction": 0.25, "source": "OpenStreetMap"},
        "canopy": {"cover_gt2m": 0.1, "source": "Meta canopy height"},
        "landcover": {"source": "ESA WorldCover"},
        "dem": {"source": "Copernicus DEM"},
        "population": {"total": 512.0},
        "aoi": {"lat": 23.0, "lon": 72.5},
        "urban_centre": {
            "id": URBAN_CENTRE,
            "name": "Ahmedabad",
            "koppen": "BSh",
            "income": "LM",
            "population_2025": 7898650,
            "tiles": 365,
        },
        "tile": {"id": TILE_ID},
    }


def _met_text() -> str:
    header = (
        "iy id it imin Q* QH QE Qs Qf Wind RH Td press rain Kdn snow ldown fcld wuh xsmd lai_hr "
        "Kdiff Kdir Wd uhii"
    )
    rows = []
    for hour in range(24):
        values = [-999.0] * 25
        values[0], values[1], values[2], values[3] = 2025, 140, hour, 0
        values[11] = 30.0 + hour / 10
        values[14] = 800.0 if 6 <= hour <= 18 else 0.0
        rows.append(
            " ".join(f"{value:.4f}" if isinstance(value, float) else str(value) for value in values)
        )
    return header + "\n" + "\n".join(rows) + "\n"


def _write_raster(path: Path, field: np.ndarray) -> None:
    bands = field if field.ndim == 3 else field[np.newaxis, ...]
    profile = {
        "driver": "GTiff",
        "height": bands.shape[1],
        "width": bands.shape[2],
        "count": bands.shape[0],
        "dtype": "float32",
        "crs": "EPSG:32643",
        "transform": from_origin(249_000.0, 2_548_000.0, 1.0, 1.0),
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(bands.astype("float32"))
