"""The measured results, assembled from the walkthrough payload; the page carries no typed numbers.

Every figure on the results page is derived here from the scored plans of every tile with
physics and from the experiment files when they exist; the engine time comes with each tile's
report. The page renders this payload in the browser; nothing on it is written by hand.
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import findings

logger = logging.getLogger(__name__)

THRESHOLD_C = 45.0
CLUSTERED, SCATTERED = "clustered", "scattered"


def collect(index_cities: list[dict], data_root: Path) -> dict:
    """The results payload: cities with their plans and derived verdicts, plus the experiments."""
    cities = [city_record(city) for city in index_cities]
    # A tile with a baseline but no scored plan yet has nothing to say here.
    cities = [city for city in cities if city["plans"]]
    plans = [plan for city in cities for plan in city["plans"]]
    costs = [plan["cost_m"] for plan in plans]
    return {
        "threshold_C": THRESHOLD_C,
        "cities": cities,
        "totals": {
            "cities": len(cities),
            "plans": len(plans),
            "budget_min_m": min(costs) if costs else None,
            "budget_max_m": max(costs) if costs else None,
        },
        "arrangement": arrangement_verdict(cities),
        "ranking": city_ranking(cities),
        "factorial": findings.load_json(Path(data_root) / "factorial.json"),
        "targeting": findings.load_json(Path(data_root) / "targeting.json"),
        "channel": findings.load_json(Path(data_root) / "channel.json"),
    }


def city_record(city: dict) -> dict:
    """One city's facts, baseline and plans, in the shape the page draws."""
    provenance = city.get("provenance", {})
    plans = [dict(plan) for plan in city.get("plans", {}).get("list", [])]
    return {
        "key": city.get("city"),
        "name": city.get("name"),
        "tile": provenance.get("urban_centre", {}).get("tile")
        if provenance.get("urban_centre")
        else None,
        "facts": {
            "canopy": provenance.get("canopy"),
            "built_fraction": provenance.get("built_fraction"),
            "population_2020": provenance.get("population_2020"),
            "tier": provenance.get("tier"),
            "design_day": provenance.get("design_day"),
        },
        "baseline": city.get("baseline", {}),
        "plans": plans,
        "physics": city.get("physics", {}),
        "matched": matched_pair(plans),
    }


def matched_pair(plans: list[dict]) -> dict | None:
    """The clustered and scattered plans closest in coverage, and the ratio of their efficiency.

    Same trees, same money: the fairest comparison of arrangements is at the same coverage, so
    the pair with the smallest coverage gap is the one quoted.
    """
    clustered = [p for p in plans if p.get("arrangement") == CLUSTERED]
    scattered = [p for p in plans if p.get("arrangement") == SCATTERED]
    if not clustered or not scattered:
        return None
    # The closest pair in coverage; among ties the largest, where ratios are most stable.
    best = min(
        ((c, s) for c in clustered for s in scattered),
        key=lambda pair: (abs(pair[0]["coverage"] - pair[1]["coverage"]), -pair[0]["coverage"]),
    )
    cluster_plan, scatter_plan = best
    ratio = (
        scatter_plan["efficiency"] / cluster_plan["efficiency"]
        if cluster_plan.get("efficiency")
        else None
    )
    return {
        "clustered": cluster_plan,
        "scattered": scatter_plan,
        "ratio": round(ratio, 2) if ratio is not None else None,
    }


def arrangement_verdict(cities: list[dict]) -> dict:
    """How many cities see scattered beat clustered per dollar at matched coverage, and by how much.

    Measured on the pair of plans closest in coverage in each city.
    """
    ratios: dict[str, float] = {}
    for city in cities:
        matched = city.get("matched") or {}
        if matched.get("ratio") is not None:
            ratios[str(city["key"])] = float(matched["ratio"])
    wins = [key for key, ratio in ratios.items() if ratio > 1]
    return {
        "ratios": ratios,
        "cities_compared": len(ratios),
        "scattered_wins": len(wins),
        "ratio_min": round(min(ratios.values()), 2) if ratios else None,
        "ratio_max": round(max(ratios.values()), 2) if ratios else None,
    }


def city_ranking(cities: list[dict]) -> dict:
    """Cities by cooling per dollar of their scattered plans, and the spread top to bottom."""
    rows = []
    for city in cities:
        scattered = [p["efficiency"] for p in city["plans"] if p.get("arrangement") == SCATTERED]
        clustered = [p["efficiency"] for p in city["plans"] if p.get("arrangement") == CLUSTERED]
        if not scattered and not clustered:
            continue
        rows.append(
            {
                "key": city["key"],
                "name": city["name"],
                "scattered_per_1k": round(_median(scattered), 2) if scattered else None,
                "clustered_per_1k": round(_median(clustered), 2) if clustered else None,
                "gain": (
                    round(_median(scattered) / _median(clustered), 2)
                    if scattered and clustered and _median(clustered)
                    else None
                ),
                "canopy": city["facts"].get("canopy"),
                "built_fraction": city["facts"].get("built_fraction"),
            }
        )
    rows.sort(key=lambda row: row["scattered_per_1k"] or row["clustered_per_1k"] or 0, reverse=True)
    spread = None
    values = [row["scattered_per_1k"] for row in rows if row["scattered_per_1k"]]
    if len(values) >= 2 and min(values) > 0:
        spread = round(max(values) / min(values), 1)
    return {"rows": rows, "spread": spread}


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2)
