"""Generate surrogate training data by running designed interventions through the physics.

One entry is a (placement, delta Tmrt) pair over the whole study area, produced by
one engine call. Sparse probe designs make each call yield many independent
single-intervention responses rather than one, which is what keeps the physics
budget affordable.

Everything is written to disk as it completes, so a long generation run can be
interrupted and resumed without losing work.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path

import numpy as np
import rasterio

from ..data.landcover import to_umep
from ..interventions import apply, feasibility_mask
from ..pipeline import BUNDLE_FILES, daylight_mean, read_band
from ..sim.runner import run
from . import designs

logger = logging.getLogger(__name__)


def default_plan() -> list[dict]:
    """The standard generation plan for one city.

    Four probe lattices at different offsets give clean isolated responses across
    varied geometry. The dense families then supply the interaction signal, which
    is the part no single-tree kernel can predict.
    """
    plan: list[dict] = []
    for seed in range(4):
        plan.append({"family": "sparse_probe", "seed": seed, "params": {}})
    for coverage in (0.01, 0.02, 0.05, 0.10, 0.20, 0.30):
        plan.append(
            {
                "family": "clustered",
                "seed": 100 + int(coverage * 100),
                "params": {"coverage": coverage, "blob_m": 20.0},
            }
        )
    for coverage in (0.01, 0.05, 0.10, 0.20):
        plan.append(
            {
                "family": "random_uniform",
                "seed": 200 + int(coverage * 100),
                "params": {"coverage": coverage},
            }
        )
    for coverage in (0.02, 0.05, 0.10):
        plan.append(
            {
                "family": "corridor",
                "seed": 300 + int(coverage * 100),
                "params": {"coverage": coverage},
            }
        )
    return plan


def make_placement(family: str, feasible: np.ndarray, seed: int, params: dict) -> np.ndarray:
    """Build one placement from a design family."""
    rng = np.random.default_rng(seed)
    builder = getattr(designs, family, None)
    if builder is None:
        raise KeyError(f"unknown design family {family!r}, expected one of {designs.FAMILIES}")
    return builder(feasible, rng, **params)


def entry_id(family: str, seed: int) -> str:
    return f"{family}_{seed:04d}"


def generate(
    bundle: Path, out_dir: Path, plan: list[dict] | None = None, kind: str = "tree"
) -> dict:
    """Run every design in the plan and store the resulting response fields."""
    bundle, out_dir = Path(bundle), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    provenance = json.loads((bundle / "provenance.json").read_text())
    design_day = provenance["met"]["design_day"]
    plan = plan if plan is not None else default_plan()

    building_dsm, _ = read_band(bundle / "Building_DSM.tif")
    terrain, _ = read_band(bundle / "DEM.tif")
    canopy, profile = read_band(bundle / "Trees.tif")
    land_cover, _ = read_band(bundle / "landcover.tif")
    building_height = np.maximum(building_dsm - terrain, 0)
    umep_cover = to_umep(land_cover, building_height)
    feasible = feasibility_mask(umep_cover, building_height, kind)

    baseline_dir = out_dir / "baseline"
    if not (baseline_dir / "tmrt_daylight.npy").exists():
        for name in BUNDLE_FILES:
            baseline_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(bundle / name, baseline_dir / name)
        logger.info("%s: baseline physics", bundle.name)
        baseline_run = run(baseline_dir, design_day)
        np.save(baseline_dir / "tmrt_daylight.npy", daylight_mean(baseline_run.tmrt_path))
    baseline_tmrt = np.load(baseline_dir / "tmrt_daylight.npy")

    manifest: list[dict] = []
    profile.update(dtype="float32", count=1)

    for index, spec in enumerate(plan, start=1):
        name = entry_id(spec["family"], spec["seed"])
        target = out_dir / name
        if (target / "response.npz").exists():
            logger.info("[%d/%d] %s already generated, skipping", index, len(plan), name)
            manifest.append(json.loads((target / "meta.json").read_text()))
            continue

        placement = make_placement(spec["family"], feasible, spec["seed"], spec["params"])
        if not placement.any():
            logger.warning("design %s produced an empty placement, skipping", name)
            continue

        target.mkdir(parents=True, exist_ok=True)
        for fname in BUNDLE_FILES:
            shutil.copy(bundle / fname, target / fname)
        new_canopy, _ = apply(kind, placement, canopy, umep_cover)
        with rasterio.open(target / "Trees.tif", "w", **profile) as destination:
            destination.write(new_canopy.astype("float32"), 1)

        started = time.time()
        engine_run = run(target, design_day)
        response = baseline_tmrt - daylight_mean(engine_run.tmrt_path)

        np.savez_compressed(
            target / "response.npz", placement=placement, response=response.astype("float32")
        )
        meta = {
            "id": name,
            "family": spec["family"],
            "seed": spec["seed"],
            "params": spec["params"],
            "kind": kind,
            "city": bundle.name,
            "design_day": design_day,
            "placed_px": int(placement.sum()),
            "coverage": round(float(placement.mean()), 5),
            "mean_response_C": round(float(response[placement].mean()), 3),
            "engine_seconds": round(time.time() - started, 1),
        }
        (target / "meta.json").write_text(json.dumps(meta, indent=2))
        manifest.append(meta)
        logger.info(
            "[%d/%d] %s: %d px, mean %.2f C, %.0fs",
            index,
            len(plan),
            name,
            meta["placed_px"],
            meta["mean_response_C"],
            meta["engine_seconds"],
        )

        # The engine writes a large multi-band stack per run; keep only what the
        # surrogate needs so a full generation does not fill the disk.
        shutil.rmtree(target / "output_folder", ignore_errors=True)
        shutil.rmtree(target / "processed_inputs", ignore_errors=True)

    summary = {
        "city": bundle.name,
        "kind": kind,
        "entries": len(manifest),
        "design_day": design_day,
        "manifest": manifest,
    }
    (out_dir / "manifest.json").write_text(json.dumps(summary, indent=2))
    return summary
