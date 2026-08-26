"""Which intervention type buys the most outdoor cooling per dollar?

Runs the design set out in PREREGISTRATION.md. The albedo-based types, cool roofs
and reflective pavement, are **excluded**: raising ground albedo in this engine cools
pedestrians by 2.59 C where a hand calculation from the model's own constants gives
+0.83 C warming and field measurement gives +4.5 to +5.8 C warming. Until that is
resolved, any number about them would be indefensible, so H1 is recorded as falsified
and H2 as untestable rather than answered with a figure nobody should trust.

What remains are the geometry-based types, trees and shade structures, which act by
adding canopy rather than by changing surface reflectivity and are unaffected.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path

import numpy as np
import rasterio

from ..baselines import orchard
from ..data.landcover import to_umep
from ..exposure import outdoor_mask, outdoor_weights
from ..interventions import apply
from ..objectives import benefit, score
from ..pipeline import BUNDLE_FILES, daylight_mean
from ..repair import building_height
from ..sim.runner import run

logger = logging.getLogger(__name__)

BUDGETS_USD = (500_000.0, 2_288_000.0, 9_100_000.0)
# Trees at 8 m is the spacing already measured as optimal and matching practice.
# Shade structures are placed further apart because each covers more ground.
TYPES = (
    {"kind": "tree", "radius_m": 3.0, "spacing_m": 8.0},
    {"kind": "shade", "radius_m": 2.8, "spacing_m": 10.0},
)


def city_layers(bundle: Path, surrogate_dir: Path) -> dict:
    def read(name: str) -> np.ndarray:
        with rasterio.open(Path(bundle) / name) as src:
            return src.read(1)

    heights = building_height(bundle)
    population = read("population.tif")
    return {
        "heights": heights,
        "canopy": read("Trees.tif"),
        "umep": to_umep(read("landcover.tif"), heights),
        "outdoor": outdoor_mask(heights),
        "weights": outdoor_weights(population, heights),
        "baseline": np.load(Path(surrogate_dir) / "baseline" / "tmrt_daylight.npy"),
        "profile": rasterio.open(Path(bundle) / "Trees.tif").profile,
    }


def run_cell(
    city: str,
    bundle: Path,
    layers: dict,
    *,
    spec: dict,
    budget: float,
    design_day: str,
    work_root: Path,
) -> dict:
    """One factorial cell: place, simulate, score."""
    placement, spent, count = orchard.select(
        budget,
        layers["baseline"],
        weights=layers["weights"],
        umep_lc=layers["umep"],
        building_h=layers["heights"],
        spacing_m=spec["spacing_m"],
        crown_radius_m=spec["radius_m"],
        kind=spec["kind"],
    )
    if count == 0:
        return {"city": city, "kind": spec["kind"], "budget": budget, "placed": 0}

    work = work_root / f"{city}_{spec['kind']}_{int(budget / 1000)}k"
    work.mkdir(parents=True, exist_ok=True)
    for name in BUNDLE_FILES:
        shutil.copy(Path(bundle) / name, work / name)

    new_canopy, _ = apply(spec["kind"], placement, layers["canopy"], layers["umep"])
    profile = dict(layers["profile"])
    profile.update(dtype="float32", count=1)
    with rasterio.open(work / "Trees.tif", "w", **profile) as dst:
        dst.write(new_canopy.astype("float32"), 1)

    started = time.time()
    result = run(work, design_day)
    tmrt = daylight_mean(result.tmrt_path)

    baseline_score = score(
        np.where(layers["outdoor"], layers["baseline"], 0), layers["weights"], 0.0
    )
    after = score(np.where(layers["outdoor"], tmrt, 0), layers["weights"], spent)
    gain = benefit(baseline_score, after)

    shutil.rmtree(work / "output_folder", ignore_errors=True)
    shutil.rmtree(work / "processed_inputs", ignore_errors=True)

    return {
        "city": city,
        "kind": spec["kind"],
        "budget_usd": budget,
        "units": count,
        "canopy_m2": int(placement.sum()),
        "spent_usd": round(spent),
        "exposure_drop_C": gain["delta_exposure_C"],
        "people": round(gain["delta_people_at_risk"]),
        "efficiency": gain["excess_reduced_per_1k_usd"],
        "engine_seconds": round(time.time() - started, 1),
    }


def run_factorial(cities: list[tuple[str, Path, Path]], out_path: Path) -> list[dict]:
    """Every type by every budget by every city."""
    rows: list[dict] = []
    total = len(cities) * len(TYPES) * len(BUDGETS_USD)
    index = 0
    for city, bundle, surrogate_dir in cities:
        layers = city_layers(bundle, surrogate_dir)
        design_day = json.loads((Path(bundle) / "provenance.json").read_text())["met"]["design_day"]
        for spec in TYPES:
            for budget in BUDGETS_USD:
                index += 1
                logger.info(
                    "[%d/%d] %s %s at %.1fM", index, total, city, spec["kind"], budget / 1e6
                )
                rows.append(
                    run_cell(
                        city,
                        bundle,
                        layers,
                        spec=spec,
                        budget=budget,
                        design_day=design_day,
                        work_root=Path("out/factorial"),
                    )
                )
                Path(out_path).write_text(json.dumps(rows, indent=2))
    return rows
