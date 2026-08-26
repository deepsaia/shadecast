"""Build the static bundle the walkthrough serves.

Everything the browser needs is precomputed to disk: one JSON index plus a handful of
greyscale atlases. There is no application logic on the server, so the bundle is a pile
of plain files that can be zipped, archived beside a paper, or published to GitHub Pages
without a build step or a CDN.

Fields ship as data rather than as pictures. See `encode`: the colour ramp is applied in
the browser, which is what lets a visitor hover a pixel and read its temperature, scrub
the day without a network round trip, and download one file instead of twenty four.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import rasterio

from ..experiments.factorial import verdict as factorial_verdict
from ..exposure import outdoor_mask, outdoor_weights
from ..interventions import cost
from ..objectives import benefit, score
from . import encode, findings

logger = logging.getLogger(__name__)

TILE_PX = 320
ARRANGEMENT = {"clustered": "clustered", "random": "scattered", "corridor": "corridor"}


def read(path: Path, band: int = 1) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(band)


def hourly_atlas(tmrt_path: Path, out_dir: Path, city: str) -> dict:
    """Every hour of the design day in one greyscale sheet, on one shared scale.

    One scale across the whole day is deliberate. Rescaling each hour to its own range
    would hide the very thing the animation exists to show, which is that the city heats
    and cools while the shade pattern sweeps across it.
    """
    with rasterio.open(tmrt_path) as src:
        bands = [src.read(b + 1) for b in range(src.count)]
    meta = encode.atlas(bands, out_dir / f"{city}_hours.png", size=TILE_PX, columns=6)
    meta["hours"] = [
        {"hour": h, "median": round(float(np.median(f)), 1), "max": round(float(f.max()), 1)}
        for h, f in enumerate(bands)
    ]
    return meta


def plan_entries(city: str, surrogate_dir: Path, out_dir: Path, layers: dict) -> dict:
    """Score every generated plan, and pack their fields into two atlases."""
    baseline = score(np.where(layers["outdoor"], layers["baseline"], 0), layers["weights"], 0.0)
    responses = sorted(surrogate_dir.glob("*/response.npz"))

    entries, cooling, placement = [], [], []
    for path in responses:
        design = path.parent.name
        family = ARRANGEMENT.get(design.split("_")[0])
        if family is None:
            continue
        payload = np.load(path)
        place, response = payload["placement"], payload["response"]
        spent = cost("tree", place, 1.0)
        gain = benefit(
            baseline,
            score(
                np.where(layers["outdoor"], layers["baseline"] - response, 0),
                layers["weights"],
                spent,
            ),
        )
        entries.append(
            {
                "id": design,
                "arrangement": family,
                "coverage": round(float(place.mean()), 4),
                "trees": int(place.sum()),
                "cost_m": round(spent / 1e6, 2),
                "exposure_drop": gain["delta_exposure_C"],
                "people": round(gain["delta_people_at_risk"]),
                "efficiency": gain["excess_reduced_per_1k_usd"],
            }
        )
        cooling.append(response)
        placement.append(place.astype(np.float32))

    order = sorted(
        range(len(entries)), key=lambda i: (entries[i]["arrangement"], entries[i]["coverage"])
    )
    entries = [entries[i] for i in order]
    for slot, entry in enumerate(entries):
        entry["tile"] = slot
    return {
        "list": entries,
        "cooling": encode.atlas(
            [cooling[i] for i in order], out_dir / f"{city}_cool.png", size=TILE_PX, columns=5
        ),
        "placement": encode.atlas(
            [placement[i] for i in order], out_dir / f"{city}_place.png", size=TILE_PX, columns=5
        ),
    }


def build_city(city: str, bundle: Path, surrogate_dir: Path, out_dir: Path) -> dict:
    """Assemble one city's payload."""
    bundle, surrogate_dir, out_dir = Path(bundle), Path(surrogate_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    provenance = json.loads((bundle / "provenance.json").read_text())

    heights = np.maximum(read(bundle / "Building_DSM.tif") - read(bundle / "DEM.tif"), 0)
    population = read(bundle / "population.tif")
    layers = {
        "building_height": heights,
        "outdoor": outdoor_mask(heights),
        "weights": outdoor_weights(population, heights),
        "baseline": np.load(surrogate_dir / "baseline" / "tmrt_daylight.npy"),
    }

    tmrt_path = surrogate_dir / "baseline" / "output_folder" / "0_0" / "TMRT_0_0.tif"
    hours = hourly_atlas(tmrt_path, out_dir, city) if tmrt_path.exists() else {}
    context = encode.atlas([heights], out_dir / f"{city}_ctx.png", size=TILE_PX, columns=1)

    baseline_score = score(
        np.where(layers["outdoor"], layers["baseline"], 0), layers["weights"], 0.0
    )
    met = np.loadtxt(bundle / "met.txt", skiprows=1)

    logger.info("%s: %d hourly frames", city, hours.get("count", 0))
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
        "met": [
            {"hour": int(r[2]), "air_c": round(float(r[11]), 1), "solar": round(float(r[14]), 0)}
            for r in met
        ],
        "hours": hours,
        "context": context,
        "plans": plan_entries(city, surrogate_dir, out_dir, layers),
    }


def build_index(cities: list[tuple[str, Path, Path]], out_dir: Path, data_root: Path) -> dict:
    """Build every city plus the findings panel, and write index.json."""
    out_dir = Path(out_dir)
    rows = findings.load_json(Path(data_root) / "factorial.json")
    verdict = factorial_verdict(rows) if isinstance(rows, list) and rows else {}

    payload = {
        "cities": [build_city(c, b, s, out_dir) for c, b, s in cities],
        "findings": findings.collect(Path(data_root), verdict),
    }
    (out_dir / "index.json").write_text(json.dumps(payload, separators=(",", ":")))
    logger.info("index.json written with %d cities", len(payload["cities"]))
    return payload
