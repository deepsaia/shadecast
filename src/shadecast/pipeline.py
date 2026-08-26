"""Run one plan-and-evaluate cycle over a built bundle.

Copies the bundle twice, runs the physics on the untouched baseline, builds a plan
against that baseline, runs the physics again on the perturbed geometry, and scores
the difference. Everything the benchmark reports comes out of this cycle.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import numpy as np
import rasterio

from . import interventions
from .baselines.greedy import select as greedy_select
from .data.landcover import to_umep
from .exposure import outdoor_mask, outdoor_weights
from .objectives import benefit, score
from .sim.runner import run

logger = logging.getLogger(__name__)

# 08:00 to 18:00. Night Tmrt is just air temperature and carries no intervention
# signal, so averaging it in would dilute every result.
DAYLIGHT_BANDS = range(8, 19)
BUNDLE_FILES = ("Building_DSM.tif", "DEM.tif", "Trees.tif", "met.txt")


def read_band(path: Path, band: int = 1) -> tuple[np.ndarray, dict]:
    """Read one raster band and its profile."""
    with rasterio.open(path) as source:
        return source.read(band), source.profile


def daylight_mean(tmrt_path: Path) -> np.ndarray:
    """Mean Tmrt across the daylight hours of the design day."""
    with rasterio.open(tmrt_path) as source:
        bands = [b for b in DAYLIGHT_BANDS if b < source.count]
        return np.mean([source.read(b + 1) for b in bands], axis=0)


def stage_bundle(source: Path, destination: Path) -> None:
    """Copy the engine inputs a run needs into a working directory."""
    destination.mkdir(parents=True, exist_ok=True)
    for name in BUNDLE_FILES:
        shutil.copy(source / name, destination / name)


def evaluate(
    bundle: Path, kind: str = "tree", budget_usd: float = 10_000_000, work_root: Path | None = None
) -> dict:
    """Plan, simulate and score one intervention against the do-nothing baseline."""
    bundle = Path(bundle)
    provenance = json.loads((bundle / "provenance.json").read_text())
    design_day = provenance["met"]["design_day"]
    resolution = provenance["aoi"]["res_m"]

    root = Path(work_root) if work_root else Path("out/runs")
    baseline_dir = root / f"{bundle.name}_baseline"
    plan_dir = root / f"{bundle.name}_{kind}"
    stage_bundle(bundle, baseline_dir)
    stage_bundle(bundle, plan_dir)

    logger.info("%s: baseline physics for design day %s", bundle.name, design_day)
    baseline_run = run(baseline_dir, design_day)
    baseline_tmrt = daylight_mean(baseline_run.tmrt_path)
    np.save(baseline_dir / "tmrt_daylight.npy", baseline_tmrt)

    building_dsm, _ = read_band(bundle / "Building_DSM.tif")
    terrain, _ = read_band(bundle / "DEM.tif")
    canopy, profile = read_band(bundle / "Trees.tif")
    land_cover, _ = read_band(bundle / "landcover.tif")
    population, _ = read_band(bundle / "population.tif")

    building_height = np.maximum(building_dsm - terrain, 0)
    umep_cover = to_umep(land_cover, building_height)
    weights = outdoor_weights(population, building_height, res_m=resolution)
    outdoors = outdoor_mask(building_height)

    placement, spent, pixels = greedy_select(
        kind,
        budget_usd,
        baseline_tmrt,
        weights=weights,
        umep_lc=umep_cover,
        building_h=building_height,
        res_m=resolution,
    )
    new_canopy, _ = interventions.apply(kind, placement, canopy, umep_cover)
    profile.update(dtype="float32", count=1)
    with rasterio.open(plan_dir / "Trees.tif", "w", **profile) as destination:
        destination.write(new_canopy.astype("float32"), 1)
    np.save(plan_dir / "placement.npy", placement)

    logger.info("%s: plan %s over %d pixels for %.0f USD", bundle.name, kind, pixels, spent)
    plan_run = run(plan_dir, design_day)
    plan_tmrt = daylight_mean(plan_run.tmrt_path)
    np.save(plan_dir / "tmrt_daylight.npy", plan_tmrt)

    baseline_score = score(np.where(outdoors, baseline_tmrt, 0), weights, 0.0)
    plan_score = score(np.where(outdoors, plan_tmrt, 0), weights, spent)
    cooling = baseline_tmrt - plan_tmrt
    planted = placement.any()

    result = {
        "city": bundle.name,
        "tier": provenance["quality"]["tier"],
        "design_day": design_day,
        "intervention": kind,
        "pixels": pixels,
        "baseline": baseline_score.as_dict(),
        "plan": plan_score.as_dict(),
        "benefit": benefit(baseline_score, plan_score),
        "tmrt_drop_where_planted_C": round(float(cooling[placement].mean()), 2) if planted else 0.0,
        "tmrt_drop_all_outdoor_C": round(float(cooling[outdoors].mean()), 2),
        "spillover_C": (round(float(cooling[outdoors & ~placement].mean()), 2) if planted else 0.0),
        "engine_seconds": {
            "baseline": round(baseline_run.seconds, 1),
            "plan": round(plan_run.seconds, 1),
        },
    }
    (plan_dir / "result.json").write_text(json.dumps(result, indent=2))
    return result
