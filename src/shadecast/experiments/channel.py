"""Does the surface temperature channel cool, and does it behave like its own parameter?

Tests H5 and H6. Converting sealed surface to grass moves the UMEP surface temperature
coefficient from 0.58 to 0.21 while changing albedo only from 0.18 to 0.16, so cooling
here arrives as reduced upwelling longwave rather than as shortwave redirected at
somebody. That is why this channel stays usable while the albedo arms are quarantined.

**The control matters more than the treatment here.** Every cell in this experiment runs
the engine with a land cover raster, and the stored baseline field was produced without
one. Comparing a treated run against that baseline would measure "land cover switched on"
alongside "asphalt became grass", and the two are not separable after the fact. So each
city pays for one extra engine run: the untouched land cover, through the identical code
path. Every reported change is against that matched control.

Placement uses the pixel planner rather than the crown planner, and for once that is
correct. One pixel really is one square metre of converted ground, unlike a tree, where
treating a pixel as a unit is what produced the retracted spacing result.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path

import numpy as np
import rasterio

from ..baselines import greedy
from ..interventions import apply
from ..objectives import benefit, score
from ..pipeline import BUNDLE_FILES, daylight_mean
from ..sim.runner import run
from .layers import city_layers

logger = logging.getLogger(__name__)

LANDCOVER_FILE = "landcover_umep.tif"
# Ordered by surface temperature coefficient, coolest first. H6 predicts the measured
# cooling follows this same order.
KINDS = ("depave", "permeable")
TS_DEG = {"depave": 0.21, "permeable": 0.37, "asphalt": 0.58}


def _stage(bundle: Path, layers: dict, umep_lc: np.ndarray, work: Path) -> None:
    """Copy a bundle and write the land cover the engine should read.

    float32, never an integer type. The engine substitutes float albedos into a copy of
    this grid, so an integer raster silently truncates every albedo to zero.
    """
    work.mkdir(parents=True, exist_ok=True)
    for name in BUNDLE_FILES:
        shutil.copy(Path(bundle) / name, work / name)
    profile = dict(layers["profile"])
    profile.update(dtype="float32", count=1)
    with rasterio.open(work / LANDCOVER_FILE, "w", **profile) as dst:
        dst.write(umep_lc.astype("float32"), 1)


def _simulate(bundle: Path, layers: dict, umep_lc: np.ndarray, work: Path, day: str) -> np.ndarray:
    _stage(bundle, layers, umep_lc, work)
    result = run(work, day, landcover=LANDCOVER_FILE)
    tmrt = daylight_mean(result.tmrt_path)
    shutil.rmtree(work / "output_folder", ignore_errors=True)
    shutil.rmtree(work / "processed_inputs", ignore_errors=True)
    return tmrt


def run_city(city: str, bundle: Path, layers: dict, *, budget: float, work_root: Path) -> dict:
    """The matched control plus one cell per surface temperature arm."""
    day = json.loads((Path(bundle) / "provenance.json").read_text())["met"]["design_day"]
    started = time.time()

    control = _simulate(bundle, layers, layers["umep"], work_root / f"{city}_control", day)
    logger.info("%s: matched control done, mean Tmrt %.2f C", city, float(np.nanmean(control)))

    cells = []
    for kind in KINDS:
        placement, spent, pixels = greedy.select(
            kind,
            budget,
            layers["baseline"],
            weights=layers["weights"],
            umep_lc=layers["umep"],
            building_h=layers["heights"],
        )
        if pixels == 0:
            cells.append({"kind": kind, "pixels": 0})
            continue
        _, new_lc = apply(kind, placement, layers["canopy"], layers["umep"])
        tmrt = _simulate(bundle, layers, new_lc, work_root / f"{city}_{kind}", day)

        gain = benefit(
            score(np.where(layers["outdoor"], control, 0), layers["weights"], 0.0),
            score(np.where(layers["outdoor"], tmrt, 0), layers["weights"], spent),
        )
        treated = float(np.nanmean(control[placement]) - np.nanmean(tmrt[placement]))
        cells.append(
            {
                "kind": kind,
                "ts_deg": TS_DEG[kind],
                "pixels": pixels,
                "area_m2": pixels,
                "spent_usd": round(spent),
                "treated_drop_C": round(treated, 4),
                "exposure_drop_C": gain["delta_exposure_C"],
                "efficiency": gain["excess_reduced_per_1k_usd"],
            }
        )
        logger.info("%s %s: treated pixels cooled %.3f C", city, kind, treated)

    return {
        "city": city,
        "budget_usd": budget,
        "control_mean_tmrt_C": round(float(np.nanmean(control)), 4),
        "cells": cells,
        "engine_seconds": round(time.time() - started, 1),
    }


def verdict(rows: list[dict]) -> dict:
    """Apply the pre-registered H5 and H6 rules."""
    cells = [c for r in rows for c in r.get("cells", []) if c.get("pixels", 0) > 0]
    if not cells:
        return {"conclusive": False}
    by_kind = {kind: [c["treated_drop_C"] for c in cells if c["kind"] == kind] for kind in KINDS}
    means = {kind: float(np.mean(v)) for kind, v in by_kind.items() if v}
    grass = means.get("depave")
    cobble = means.get("permeable")
    result = {
        "conclusive": True,
        "cities": len(rows),
        "mean_treated_drop_C": {k: round(v, 4) for k, v in means.items()},
        # H5: de-paving cools, predicted 0.5 to 3 C at treated pixels.
        "h5_cools": grass is not None and grass > 0,
        "h5_in_predicted_range": grass is not None and 0.5 <= grass <= 3.0,
        "h5_falsified": grass is not None and grass < 0,
    }
    if grass is not None and cobble is not None:
        # H6: cooling must follow the surface temperature coefficient, grass over cobble.
        result["h6_monotone"] = grass > cobble > 0
        result["h6_falsified"] = cobble > grass
    return result


def run_channel(cities: list[tuple[str, Path, Path]], out_path: Path, *, budget: float) -> dict:
    """Every surface temperature arm in every city, each against its own control."""
    rows: list[dict] = []
    for index, (city, bundle, surrogate_dir) in enumerate(cities, start=1):
        logger.info("[%d/%d] %s at %.1fM", index, len(cities), city, budget / 1e6)
        rows.append(
            run_city(
                city,
                bundle,
                city_layers(bundle, surrogate_dir),
                budget=budget,
                work_root=Path("out/channel"),
            )
        )
        running = {"rows": rows, "verdict": verdict(rows), "complete": False}
        Path(out_path).write_text(json.dumps(running, indent=2))
    # Only now is the result a finding rather than a run in progress.
    payload = {"rows": rows, "verdict": verdict(rows), "complete": True}
    Path(out_path).write_text(json.dumps(payload, indent=2))
    return payload
