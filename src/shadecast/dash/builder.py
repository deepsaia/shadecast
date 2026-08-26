"""Build the static bundle the dashboard serves.

Everything the browser needs is precomputed to disk: one JSON index plus PNG frames.
The server is then a plain static file server with no application logic, which keeps
the dependency surface at zero beyond the standard library and makes the whole
bundle trivially publishable or archived alongside a paper.

The hourly Tmrt frames are the reason this exists. A single map of a design day
hides the thing that actually matters, which is that the shade pattern sweeps across
the city as the sun moves. Scrubbing through 24 frames shows that directly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import rasterio

from .. import viz
from ..exposure import outdoor_mask, outdoor_weights
from ..interventions import cost
from ..objectives import benefit, score

logger = logging.getLogger(__name__)

FRAME_PX = 420
MAP_PX = 460
ARRANGEMENT = {"clustered": "clustered", "random": "scattered", "corridor": "corridor"}


def read(path: Path, band: int = 1) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(band)


def hourly_frames(tmrt_path: Path, out_dir: Path, city: str) -> list[dict]:
    """Render one PNG per hour on a single shared scale across the whole day."""
    with rasterio.open(tmrt_path) as src:
        bands = [src.read(b + 1) for b in range(src.count)]
    stacked = np.stack(bands)
    # One scale for all 24 hours, or the animation would rescale itself and hide
    # the very thing it exists to show.
    vmin, vmax = float(stacked.min()), float(stacked.max())
    frames = []
    for hour, field in enumerate(bands):
        name = f"{city}_tmrt_{hour:02d}.png"
        viz.temperature(field, out_dir / name, vmin=vmin, vmax=vmax, size_px=FRAME_PX)
        frames.append(
            {
                "hour": hour,
                "img": name,
                "min": round(float(field.min()), 1),
                "median": round(float(np.median(field)), 1),
                "max": round(float(field.max()), 1),
            }
        )
    return frames


def plan_entries(city: str, surrogate_dir: Path, out_dir: Path, layers: dict) -> list[dict]:
    """Score and render every generated plan for one city."""
    baseline = score(np.where(layers["outdoor"], layers["baseline"], 0), layers["weights"], 0.0)
    responses = sorted(surrogate_dir.glob("*/response.npz"))
    scales = []
    for path in responses:
        if path.parent.name.startswith("sparse"):
            continue
        scales.append(np.percentile(np.load(path)["response"], 99.9))
    shared_vmax = float(max(scales)) if scales else 1.0

    entries = []
    for path in responses:
        design = path.parent.name
        family = ARRANGEMENT.get(design.split("_")[0])
        if family is None:
            continue
        payload = np.load(path)
        placement, response = payload["placement"], payload["response"]
        spent = cost("tree", placement, 1.0)
        after = score(
            np.where(layers["outdoor"], layers["baseline"] - response, 0),
            layers["weights"],
            spent,
        )
        gain = benefit(baseline, after)

        place_img = f"{city}_{design}_place.png"
        cool_img = f"{city}_{design}_cool.png"
        viz.placement(
            placement, out_dir / place_img, buildings=layers["building_height"], size_px=MAP_PX
        )
        viz.cooling(
            response,
            out_dir / cool_img,
            vmax=shared_vmax,
            buildings=layers["building_height"],
            size_px=MAP_PX,
        )

        entries.append(
            {
                "id": design,
                "arrangement": family,
                "coverage": round(float(placement.mean()), 4),
                "trees": int(placement.sum()),
                "cost_m": round(spent / 1e6, 2),
                "exposure_drop": gain["delta_exposure_C"],
                "people": round(gain["delta_people_at_risk"]),
                "efficiency": gain["excess_reduced_per_1k_usd"],
                "place_img": place_img,
                "cool_img": cool_img,
            }
        )
    entries.sort(key=lambda e: (e["arrangement"], e["coverage"]))
    return entries


def build_city(city: str, bundle: Path, surrogate_dir: Path, out_dir: Path) -> dict:
    """Assemble one city's dashboard payload."""
    bundle, surrogate_dir, out_dir = Path(bundle), Path(surrogate_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    provenance = json.loads((bundle / "provenance.json").read_text())

    heights = np.maximum(read(bundle / "Building_DSM.tif") - read(bundle / "DEM.tif"), 0)
    layers = {
        "building_height": heights,
        "canopy": read(bundle / "Trees.tif"),
        "population": read(bundle / "population.tif"),
        "outdoor": outdoor_mask(heights),
        "weights": outdoor_weights(read(bundle / "population.tif"), heights),
        "baseline": np.load(surrogate_dir / "baseline" / "tmrt_daylight.npy"),
    }

    tmrt_path = surrogate_dir / "baseline" / "output_folder" / "0_0" / "TMRT_0_0.tif"
    frames = hourly_frames(tmrt_path, out_dir, city) if tmrt_path.exists() else []

    baseline_score = score(
        np.where(layers["outdoor"], layers["baseline"], 0), layers["weights"], 0.0
    )
    met = np.loadtxt(bundle / "met.txt", skiprows=1)

    logger.info("%s: %d hourly frames, scoring plans", city, len(frames))
    return {
        "city": city,
        "name": provenance["city"]["name"] if "city" in provenance else city.title(),
        "provenance": {
            "design_day": provenance["met"]["design_day"],
            "tier": provenance.get("quality", {}).get("tier", "?"),
            "buildings": provenance["buildings"]["count"],
            "built_fraction": provenance["buildings"]["built_fraction"],
            "canopy": provenance["canopy"]["cover_gt2m"],
            "population": provenance.get("population", {}).get("total"),
            "lat": provenance["aoi"]["lat"],
            "lon": provenance["aoi"]["lon"],
            "sources": {
                "buildings": provenance["buildings"]["source"],
                "terrain": provenance["dem"]["source"],
                "canopy": provenance["canopy"]["source"],
                "landcover": provenance["landcover"]["source"],
                "meteorology": provenance["met"]["source"],
            },
        },
        "baseline": {
            "exposure": round(baseline_score.exposure, 2),
            "at_risk": round(baseline_score.people_at_risk),
        },
        # Air temperature and solar for the scrubber's context strip.
        "met": [
            {"hour": int(r[2]), "air_c": round(float(r[11]), 1), "solar": round(float(r[14]), 0)}
            for r in met
        ],
        "frames": frames,
        "plans": plan_entries(city, surrogate_dir, out_dir, layers),
    }
