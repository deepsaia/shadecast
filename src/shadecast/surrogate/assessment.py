"""Judge the trained surrogate against the physics it is standing in for.

Four questions, in the order that decides whether the surrogate is usable.

1. **Does it beat predicting nothing?** The response is near zero almost everywhere,
   so a low mean error proves nothing on its own. Skill against the zero baseline is
   the first gate, and a negative value means the model is worse than useless.
2. **Does the tail survive?** Cooling reaches tens of metres, and that tail is the
   spillover the benchmark exists to measure. A model that nails the near field and
   flattens the tail would pass on mean error and fail at the job.
3. **Is the plan score right?** Plans are ranked on population weighted exposure,
   which integrates the whole field, so that integral has to be unbiased.
4. **Does it order plans correctly?** A search only needs to know which of two plans
   is better. Biased but monotone is fine; unbiased but scrambled is worthless.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
import rasterio
import torch

from ..exposure import outdoor_mask, outdoor_weights
from .features import stack
from .metrics import aggregate_error, distance_bands, ranking, skill, speedup
from .patches import entries
from .predict import load, predict_field

logger = logging.getLogger(__name__)

ENGINE_SECONDS_REFERENCE = 162.0


def _city_layers(bundle: Path) -> dict:
    with rasterio.open(bundle / "Building_DSM.tif") as src:
        building_dsm = src.read(1)
    with rasterio.open(bundle / "DEM.tif") as src:
        terrain = src.read(1)
    with rasterio.open(bundle / "Trees.tif") as src:
        canopy = src.read(1)
    with rasterio.open(bundle / "landcover.tif") as src:
        land_cover = src.read(1)
    with rasterio.open(bundle / "population.tif") as src:
        population = src.read(1)
    height = np.maximum(building_dsm - terrain, 0)
    return {
        "building_height": height,
        "canopy": canopy,
        "land_cover": land_cover,
        "population": population,
        "outdoor": outdoor_mask(height),
        "weights": outdoor_weights(population, height),
    }


def assess(
    surrogate_dir: Path,
    bundle: Path,
    only: list[str] | None = None,
    device: torch.device | None = None,
) -> dict:
    """Compare surrogate predictions against engine truth on the given designs."""
    surrogate_dir, bundle = Path(surrogate_dir), Path(bundle)
    checkpoint = surrogate_dir / "model.pt"
    if not checkpoint.exists():
        raise FileNotFoundError(f"no trained model at {checkpoint}")

    report_path = surrogate_dir / "training_report.json"
    held_out = None
    if report_path.exists():
        held_out = json.loads(report_path.read_text()).get("held_out_designs")
    wanted = only if only else held_out
    if not wanted:
        raise RuntimeError("no held-out designs recorded; train first")

    layers = _city_layers(bundle)
    baseline_tmrt = np.load(surrogate_dir / "baseline" / "tmrt_daylight.npy")
    model = load(checkpoint, device)
    target_device = device or next(model.parameters()).device

    per_design: list[dict] = []
    truth_scores: list[float] = []
    predicted_scores: list[float] = []
    total_seconds = 0.0

    known = {meta["id"] for meta in entries(surrogate_dir)}
    for design_id in wanted:
        if design_id not in known:
            logger.warning("design %s not present in %s, skipping", design_id, surrogate_dir)
            continue
        payload = np.load(surrogate_dir / design_id / "response.npz")
        placement, truth = payload["placement"], payload["response"]

        features = stack(
            placement,
            baseline_tmrt,
            building_height=layers["building_height"],
            canopy_height=layers["canopy"],
            land_cover=layers["land_cover"],
        )
        started = time.perf_counter()
        predicted = predict_field(model, features, target_device)
        elapsed = time.perf_counter() - started
        total_seconds += elapsed

        outdoor = layers["outdoor"]
        per_design.append(
            {
                "design": design_id,
                "coverage": round(float(placement.mean()), 5),
                "skill": skill(truth[outdoor], predicted[outdoor]),
                "aggregate": aggregate_error(truth, predicted, layers["weights"]),
                "bands": distance_bands(truth, predicted, placement),
                "surrogate_seconds": round(elapsed, 4),
            }
        )
        truth_scores.append(per_design[-1]["aggregate"]["truth_C"])
        predicted_scores.append(per_design[-1]["aggregate"]["predicted_C"])

    if not per_design:
        raise RuntimeError("no designs could be assessed")

    mean_seconds = total_seconds / len(per_design)
    return {
        "city": bundle.name,
        "designs_assessed": [d["design"] for d in per_design],
        "device": str(target_device),
        "headline": {
            "mean_skill": round(float(np.mean([d["skill"]["skill"] for d in per_design])), 4),
            "all_beat_predicting_nothing": all(
                d["skill"]["beats_predicting_nothing"] for d in per_design
            ),
            "mean_aggregate_relative_error": round(
                float(np.mean([d["aggregate"]["relative_error"] for d in per_design])), 4
            ),
        },
        "ranking": ranking(truth_scores, predicted_scores),
        "speed": speedup(ENGINE_SECONDS_REFERENCE, mean_seconds),
        "per_design": per_design,
    }
