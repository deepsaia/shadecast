"""Does targeting corridors select a different plan than targeting hot ground?

This is the test of H8, and it is the load-bearing experiment for the network objective.
Two plans are built at the same budget with the same intervention type. One ranks pixels
by area harm, which is excess heat times the people near it. The other ranks them by
corridor value, which is the trip heat that actually flows along the street beside them.
Both are simulated for real, and each is scored on both objectives.

If the two plans come out nearly the same, the network objective is redundant and should
be reported as a null. That outcome is cheap to hide and the pre-registration exists to
stop it being hidden, so the verdict rule is fixed here in code rather than chosen later.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path

import networkx as nx
import numpy as np
import rasterio

from ..aoi import AOI
from ..baselines import orchard
from ..interventions import apply
from ..network import graph as netgraph
from ..network import heat, rasterize, routing
from ..objectives import benefit, score
from ..pipeline import BUNDLE_FILES, daylight_mean
from ..sim.runner import run

logger = logging.getLogger(__name__)

# Fixed before any run, per the pre-registration.
ENDPOINTS = 40
SEED = 0
SPEC = {"kind": "tree", "radius_m": 3.0, "spacing_m": 8.0}
# H8 thresholds, also fixed in advance.
OVERLAP_REDUNDANT = 0.90
OVERLAP_DIFFERENT = 0.70
MIN_ADVANTAGE_C = 0.3


def score_routes(
    multigraph: nx.MultiDiGraph,
    tmrt: np.ndarray,
    aoi: AOI,
    *,
    weights: dict[int, float],
    endpoints: list[int],
) -> routing.RouteScore:
    """Re-score the same trips on a new heat field, keeping endpoints fixed."""
    heat.annotate(multigraph, tmrt, aoi)
    routing.set_perceived(multigraph)
    return routing.evaluate(routing.to_routable(multigraph), weights, endpoints)


def prepare_network(
    bundle: Path, aoi: AOI, baseline: np.ndarray, population: np.ndarray
) -> tuple[nx.MultiDiGraph, dict[int, float], list[int]]:
    """Fetch the walk network and fix the trip set once, so every plan is judged alike."""
    multigraph = netgraph.largest_component(netgraph.fetch(aoi, Path(bundle) / "network"))
    heat.annotate(multigraph, baseline, aoi)
    routing.set_perceived(multigraph)
    digraph = routing.to_routable(multigraph)
    weights = routing.node_population(digraph, population, aoi)
    endpoints = routing.sample_nodes(weights, ENDPOINTS, seed=SEED)
    logger.info(
        "network: %d nodes, %d edges, %d trip endpoints",
        digraph.number_of_nodes(),
        digraph.number_of_edges(),
        len(endpoints),
    )
    return multigraph, weights, endpoints


def plan_overlap(first: np.ndarray, second: np.ndarray) -> float:
    """Jaccard overlap of two placements. Equal budgets make the areas comparable."""
    union = int((first | second).sum())
    return float((first & second).sum() / union) if union else 1.0


def simulate(
    bundle: Path, layers: dict, placement: np.ndarray, *, work: Path, design_day: str
) -> np.ndarray:
    """Apply a placement and run the engine, returning the daylight-mean Tmrt field."""
    work.mkdir(parents=True, exist_ok=True)
    for name in BUNDLE_FILES:
        shutil.copy(Path(bundle) / name, work / name)
    new_canopy, _ = apply(SPEC["kind"], placement, layers["canopy"], layers["umep"])
    profile = dict(layers["profile"])
    profile.update(dtype="float32", count=1)
    with rasterio.open(work / "Trees.tif", "w", **profile) as dst:
        dst.write(new_canopy.astype("float32"), 1)
    result = run(work, design_day)
    tmrt = daylight_mean(result.tmrt_path)
    shutil.rmtree(work / "output_folder", ignore_errors=True)
    shutil.rmtree(work / "processed_inputs", ignore_errors=True)
    return tmrt


def run_city(
    city: str, bundle: Path, layers: dict, *, budget: float, aoi: AOI, work_root: Path
) -> dict:
    """Build both plans at one budget, simulate both, score both on both objectives."""
    design_day = json.loads((Path(bundle) / "provenance.json").read_text())["met"]["design_day"]
    baseline = layers["baseline"]
    multigraph, node_weights, endpoints = prepare_network(
        bundle, aoi, baseline, layers["population"]
    )
    base_routes = score_routes(
        multigraph, baseline, aoi, weights=node_weights, endpoints=endpoints
    )
    digraph = routing.to_routable(multigraph)
    surface = rasterize.corridor_surface(digraph, base_routes.corridor, aoi)

    common = {
        "weights": layers["weights"],
        "umep_lc": layers["umep"],
        "building_h": layers["heights"],
        "spacing_m": SPEC["spacing_m"],
        "crown_radius_m": SPEC["radius_m"],
        "kind": SPEC["kind"],
    }
    area_plan, area_spent, area_n = orchard.select(budget, baseline, **common)
    route_plan, route_spent, route_n = orchard.select(budget, baseline, surface=surface, **common)
    if area_n == 0 or route_n == 0:
        return {"city": city, "budget_usd": budget, "placed": 0}

    started = time.time()
    results = {}
    for label, plan, spent in (
        ("area", area_plan, area_spent),
        ("route", route_plan, route_spent),
    ):
        tmrt = simulate(
            bundle,
            layers,
            plan,
            work=work_root / f"{city}_{label}_{int(budget / 1000)}k",
            design_day=design_day,
        )
        gain = benefit(
            score(np.where(layers["outdoor"], baseline, 0), layers["weights"], 0.0),
            score(np.where(layers["outdoor"], tmrt, 0), layers["weights"], spent),
        )
        routes = score_routes(multigraph, tmrt, aoi, weights=node_weights, endpoints=endpoints)
        results[label] = {
            "spent_usd": round(spent),
            "trees": area_n if label == "area" else route_n,
            "area_exposure_drop_C": gain["delta_exposure_C"],
            "experienced_tmrt_C": routes.experienced_tmrt,
            "route_exposure_drop_C": base_routes.experienced_tmrt - routes.experienced_tmrt,
        }

    return {
        "city": city,
        "budget_usd": budget,
        "baseline_experienced_tmrt_C": round(base_routes.experienced_tmrt, 4),
        "baseline_detour_ratio": round(base_routes.detour_ratio, 4),
        "plan_overlap": round(plan_overlap(area_plan, route_plan), 4),
        "area": results["area"],
        "route": results["route"],
        "engine_seconds": round(time.time() - started, 1),
    }


def verdict(rows: list[dict]) -> dict:
    """Apply the pre-registered H8 rule. The thresholds were fixed before any run."""
    scored = [r for r in rows if r.get("plan_overlap") is not None]
    if not scored:
        return {"conclusive": False}
    overlaps = [r["plan_overlap"] for r in scored]
    advantages = [
        r["route"]["route_exposure_drop_C"] - r["area"]["route_exposure_drop_C"] for r in scored
    ]
    mean_overlap = float(np.mean(overlaps))
    mean_advantage = float(np.mean(advantages))
    return {
        "conclusive": True,
        "cities": len(scored),
        "mean_plan_overlap": round(mean_overlap, 4),
        "mean_route_advantage_C": round(mean_advantage, 4),
        "plans_differ": mean_overlap < OVERLAP_DIFFERENT,
        "route_targeting_helps": mean_advantage >= MIN_ADVANTAGE_C,
        "h8_falsified": mean_overlap > OVERLAP_REDUNDANT,
        "supported": mean_overlap < OVERLAP_DIFFERENT and mean_advantage >= MIN_ADVANTAGE_C,
    }
