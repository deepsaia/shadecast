"""Counts and quantiles over the corpus and over the tiles of one urban centre.

Nothing here is modelled. A statistic is a count, a sum or a quantile of what the data says,
with unknown strata reported as unknown rather than dropped, so a reader can see how much of
the corpus the stratification actually covers.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterable

import numpy as np

from .urban_centre import UrbanCentre

UNKNOWN = "unknown"
INCOME_ORDER = ("L", "LM", "UM", "H")
SIZE_BANDS: tuple[tuple[str, int, int | None], ...] = (
    ("1 to 10", 1, 10),
    ("11 to 100", 11, 100),
    ("101 to 1,000", 101, 1000),
    ("over 1,000", 1001, None),
)
PEOPLE_THRESHOLDS = (10_000, 50_000)
TOP_COUNTRIES = 10
QUANTILE_FIELDS = ("density_2020_per_km2", "built_fraction", "mean_height_m")


def _label(value: object) -> str:
    return UNKNOWN if value is None else str(value)


def _group(centres: list[UrbanCentre], name: str, key: Callable[[UrbanCentre], str]) -> list[dict]:
    """Centres, tiles and people per group, most centres first, then most people.

    Three arguments: what to group, what to call the key, and how to compute it.
    """
    groups: dict[str, dict] = {}
    for centre in centres:
        row = groups.setdefault(key(centre), {name: key(centre), "urban_centres": 0, "tiles": 0, "population_2025": 0})
        row["urban_centres"] += 1
        row["tiles"] += centre.tiles
        row["population_2025"] += centre.population_2025
    return sorted(groups.values(), key=_by_centres_then_people)


def _by_centres_then_people(row: dict) -> tuple[int, int]:
    return -int(row.get("urban_centres", 0)), -int(row.get("population_2025", 0))


def _continent(centre: UrbanCentre) -> str:
    return _label(centre.continent)


def _country(centre: UrbanCentre) -> str:
    return _label(centre.country)


def _count_by(labels: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return counts


def _by_koppen(centres: list[UrbanCentre]) -> dict[str, int]:
    counts = _count_by(_label(centre.koppen) for centre in centres)
    ordered = sorted(counts.items(), key=_by_count_then_name)
    return dict(ordered)


def _by_count_then_name(item: tuple[str, int]) -> tuple[int, str]:
    return -item[1], item[0]


def _by_income(centres: list[UrbanCentre]) -> dict[str, int]:
    counts = _count_by(_label(centre.income) for centre in centres)
    return {label: counts.get(label, 0) for label in (*INCOME_ORDER, UNKNOWN)}


def _size_bands(centres: list[UrbanCentre]) -> dict[str, int]:
    bands = {label: 0 for label, _, _ in SIZE_BANDS}
    for centre in centres:
        for label, low, high in SIZE_BANDS:
            if centre.tiles >= low and (high is None or centre.tiles <= high):
                bands[label] += 1
                break
    return bands


def corpus_stats(centres: Iterable[UrbanCentre]) -> dict:
    """Totals, continents, the ten largest countries by centres, strata and size bands."""
    listed = list(centres)
    return {
        "totals": {
            "urban_centres": len(listed),
            "tiles": sum(centre.tiles for centre in listed),
            "population_2025": sum(centre.population_2025 for centre in listed),
            "countries": len({centre.country for centre in listed}),
            "continents": len({centre.continent for centre in listed if centre.continent}),
        },
        "by_continent": _group(listed, "continent", _continent),
        "top_countries": _group(listed, "country", _country)[:TOP_COUNTRIES],
        "by_koppen": _by_koppen(listed),
        "by_income": _by_income(listed),
        "size_bands": _size_bands(listed),
    }


def _quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "p25": 0.0, "median": 0.0, "p75": 0.0, "max": 0.0}
    array = np.asarray(values, dtype="float64")
    low, p25, median, p75, high = np.percentile(array, [0, 25, 50, 75, 100])
    return {
        "min": round(float(low), 4),
        "p25": round(float(p25), 4),
        "median": round(float(median), 4),
        "p75": round(float(p75), 4),
        "max": round(float(high), 4),
    }


def tile_stats(rows: Iterable[dict]) -> dict:
    """How many tiles, how many people, and the spread of density, built fraction and height."""
    listed = list(rows)
    people = [float(row.get("population_2020", 0.0)) for row in listed]
    return {
        "tiles": len(listed),
        "populated_tiles": sum(value > 0 for value in people),
        "population_2020": round(sum(people)),
        "tiles_over": {
            f"tiles with {threshold:,} people or more": sum(value >= threshold for value in people)
            for threshold in PEOPLE_THRESHOLDS
        },
        "quantiles": {field: _quantiles([float(row.get(field, 0.0)) for row in listed]) for field in QUANTILE_FIELDS},
    }
