"""The measured results across every tile with physics, derived from tile reports, not typed in."""

from __future__ import annotations

from collections import Counter
from datetime import UTC
from datetime import datetime
from pathlib import Path

from ..objectives import TMRT_STRESS_C
from .arrangement_verdict import ArrangementVerdict
from .city_catalog import CityCatalog
from .city_result import CityResult
from .json_file import read_json
from .matched_pair import MatchedPair
from .plan import Plan
from .ranking import Ranking
from .ranking_row import RankingRow
from .results import Results
from .results_totals import ResultsTotals
from .tile_report import TileReport
from .tile_reporter import report_of

CLUSTERED, SCATTERED = "clustered", "scattered"


class ResultsReport:
    """Answers the cross-city results, from every tile with physics or from reports in hand."""

    def __init__(self, catalog: CityCatalog, data_root: Path) -> None:
        self._catalog = catalog
        self._data_root = Path(data_root)

    def collect(self) -> Results:
        """The results over every tile of every selected city that has simulated physics."""
        reports = [
            report_of(self._catalog.tile_paths(city.key, tile.tile))
            for city in self._catalog.cities()
            for tile in self._catalog.tiles_on_disk(city.key)
            if tile.stages.physics
        ]
        return self.collect_from(reports)

    def collect_from(self, reports: list[TileReport]) -> Results:
        return results_from(reports, self._data_root)


def results_from(reports: list[TileReport], data_root: Path) -> Results:
    """The results payload for reports in hand, plus the experiment files beside the tiles."""
    cities = [city for city in _city_results(reports) if city.plans]
    plans = [plan for city in cities for plan in city.plans]
    costs = [plan.cost_m for plan in plans]
    root = Path(data_root)
    return Results(
        threshold_C=TMRT_STRESS_C,
        as_of=datetime.now(UTC).strftime("%Y-%m-%d"),
        cities=cities,
        totals=ResultsTotals(
            cities=len(cities),
            plans=len(plans),
            budget_min_m=min(costs) if costs else None,
            budget_max_m=max(costs) if costs else None,
        ),
        arrangement=arrangement_verdict(cities),
        ranking=city_ranking(cities),
        factorial=read_json(root / "factorial.json"),
        targeting=read_json(root / "targeting.json"),
        channel=read_json(root / "channel.json"),
    )


def _city_results(reports: list[TileReport]) -> list[CityResult]:
    """One result per tile; a city with several tiles with physics is labeled tile by tile."""
    tiles_per_city = Counter(report.city for report in reports)
    results = []
    for report in reports:
        several = tiles_per_city.get(report.city, 0) > 1
        results.append(
            CityResult(
                key=f"{report.city}-{report.tile}" if several else report.city,
                name=f"{report.name}, tile {report.tile}" if several else report.name,
                tile=report.tile,
                facts=report.facts,
                baseline=report.baseline,
                plans=report.plans,
                physics=report.physics,
                matched=matched_pair(report.plans),
            )
        )
    return results


def matched_pair(plans: list[Plan]) -> MatchedPair | None:
    """The clustered and scattered plans closest in coverage, and the ratio of their efficiency.

    Same trees, same money: the fairest comparison of arrangements is at the same coverage, so
    the pair with the smallest coverage gap is the one quoted; among ties the largest coverage,
    where ratios are most stable.
    """
    clustered = [plan for plan in plans if plan.arrangement == CLUSTERED]
    scattered = [plan for plan in plans if plan.arrangement == SCATTERED]
    if not clustered or not scattered:
        return None
    cluster_plan, scatter_plan = min(((c, s) for c in clustered for s in scattered), key=_by_coverage_gap_then_largest)
    ratio = scatter_plan.efficiency / cluster_plan.efficiency if cluster_plan.efficiency else None
    return MatchedPair(
        clustered=cluster_plan,
        scattered=scatter_plan,
        ratio=round(ratio, 2) if ratio is not None else None,
    )


def _by_coverage_gap_then_largest(pair: tuple[Plan, Plan]) -> tuple[float, float]:
    return (abs(pair[0].coverage - pair[1].coverage), -pair[0].coverage)


def arrangement_verdict(cities: list[CityResult]) -> ArrangementVerdict:
    """How many tiles see scattered beat clustered per dollar at matched coverage, and how far."""
    ratios = {
        city.key: float(city.matched.ratio)
        for city in cities
        if city.matched is not None and city.matched.ratio is not None
    }
    return ArrangementVerdict(
        ratios=ratios,
        cities_compared=len(ratios),
        scattered_wins=sum(1 for ratio in ratios.values() if ratio > 1),
        ratio_min=round(min(ratios.values()), 2) if ratios else None,
        ratio_max=round(max(ratios.values()), 2) if ratios else None,
    )


def city_ranking(cities: list[CityResult]) -> Ranking:
    """Tiles by cooling per dollar of their scattered plans, and the spread top to bottom."""
    rows = [row for row in (_ranking_row(city) for city in cities) if row is not None]
    rows.sort(key=_by_efficiency, reverse=True)
    values = [row.scattered_per_1k for row in rows if row.scattered_per_1k]
    spread = round(max(values) / min(values), 1) if len(values) >= 2 and min(values) > 0 else None
    return Ranking(rows=rows, spread=spread)


def _ranking_row(city: CityResult) -> RankingRow | None:
    scattered = [plan.efficiency for plan in city.plans if plan.arrangement == SCATTERED]
    clustered = [plan.efficiency for plan in city.plans if plan.arrangement == CLUSTERED]
    if not scattered and not clustered:
        return None
    gain = None
    if scattered and clustered and _median(clustered):
        gain = round(_median(scattered) / _median(clustered), 2)
    return RankingRow(
        key=city.key,
        name=city.name,
        scattered_per_1k=round(_median(scattered), 2) if scattered else None,
        clustered_per_1k=round(_median(clustered), 2) if clustered else None,
        gain=gain,
        canopy=city.facts.canopy,
        built_fraction=city.facts.built_fraction,
    )


def _by_efficiency(row: RankingRow) -> float:
    return row.scattered_per_1k or row.clustered_per_1k or 0.0


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2)
