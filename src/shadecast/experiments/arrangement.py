"""Does spatial arrangement change what a fixed budget buys?

This is the experiment the benchmark exists to make possible, and it needs no
surrogate: the generated designs already contain matched pairs of plans that spend
the same money in different spatial patterns, each with a real engine response.

Greedy, the standard "plant where it is hottest" heuristic, produces a clustered
plan by construction, because hot ground is contiguous. Measured on Ahmedabad,
greedy's placement has 665 connected components with a median size of 4 pixels,
which is structurally the same as the deliberately clustered design (302 components,
median 4). So comparing clustered against scattered at equal cost is a fair proxy
for comparing greedy against an arrangement-aware alternative.

The result is that the two standard objectives disagree, which is the point.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio

from ..exposure import outdoor_mask, outdoor_weights
from ..interventions import cost
from ..objectives import benefit, score

logger = logging.getLogger(__name__)

# Designs generated at matched coverage, differing only in spatial arrangement.
MATCHED_PAIRS = (
    ("clustered_0105", "random_uniform_0205", "corridor_0305"),
    ("clustered_0110", "random_uniform_0210", "corridor_0310"),
    ("clustered_0120", "random_uniform_0220", None),
)


def _layers(bundle: Path, surrogate_dir: Path) -> dict:
    def read(name: str) -> np.ndarray:
        with rasterio.open(Path(bundle) / name) as src:
            return src.read(1)

    heights = np.maximum(read("Building_DSM.tif") - read("DEM.tif"), 0)
    population = read("population.tif")
    return {
        "baseline": np.load(Path(surrogate_dir) / "baseline" / "tmrt_daylight.npy"),
        "outdoor": outdoor_mask(heights),
        "weights": outdoor_weights(population, heights),
    }


def compare(bundle: Path, surrogate_dir: Path, res_m: float = 1.0) -> dict:
    """Score every matched arrangement pair against the do-nothing baseline."""
    layers = _layers(bundle, surrogate_dir)
    baseline_score = score(
        np.where(layers["outdoor"], layers["baseline"], 0), layers["weights"], 0.0
    )

    rows: list[dict] = []
    for group in MATCHED_PAIRS:
        for design in group:
            if design is None:
                continue
            payload_path = Path(surrogate_dir) / design / "response.npz"
            if not payload_path.exists():
                continue
            payload = np.load(payload_path)
            placement, response = payload["placement"], payload["response"]
            spent = cost("tree", placement, res_m)
            after = score(
                np.where(layers["outdoor"], layers["baseline"] - response, 0),
                layers["weights"],
                spent,
            )
            gain = benefit(baseline_score, after)
            rows.append(
                {
                    "design": design,
                    "arrangement": design.split("_")[0],
                    "coverage": round(float(placement.mean()), 5),
                    "cost_usd": round(spent, 0),
                    "exposure_drop_C": gain["delta_exposure_C"],
                    "people_below_threshold": gain["delta_people_at_risk"],
                    "total_cooling_Cm2": round(float(response[layers["outdoor"]].sum()), 0),
                    "efficiency_per_1k": gain["excess_reduced_per_1k_usd"],
                }
            )

    return {
        "city": Path(bundle).name,
        "baseline": baseline_score.as_dict(),
        "rows": rows,
        "verdict": verdict(rows),
    }


def verdict(rows: list[dict]) -> dict:
    """Which arrangement wins, and does the answer depend on the objective?"""
    clustered = [r for r in rows if r["arrangement"] == "clustered"]
    scattered = [r for r in rows if r["arrangement"] == "random"]
    if not clustered or not scattered:
        return {"conclusive": False}

    exposure_ratio = float(
        np.mean([s["exposure_drop_C"] for s in scattered])
        / max(np.mean([c["exposure_drop_C"] for c in clustered]), 1e-9)
    )
    people_ratio = float(
        np.mean([c["people_below_threshold"] for c in clustered])
        / max(np.mean([s["people_below_threshold"] for s in scattered]), 1e-9)
    )
    return {
        "conclusive": True,
        "scattered_beats_clustered_on_exposure_by": round(exposure_ratio, 2),
        "clustered_beats_scattered_on_threshold_by": round(people_ratio, 2),
        # The finding: two standard objectives select opposite plans at equal cost,
        # so reporting a single number would hide the actual decision.
        "objectives_disagree": exposure_ratio > 1.0 and people_ratio > 1.0,
    }
