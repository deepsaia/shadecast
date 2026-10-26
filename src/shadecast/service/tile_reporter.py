"""Produce a tile's report from disk once; while its sources are unchanged it is read back."""

from __future__ import annotations

import numpy as np

from ..corpus.tile_paths import TilePaths
from .city_catalog import CityCatalog
from .derived_cache import DerivedCache
from .field_store import FieldStore
from .hourly_statistic import HourlyStatistic
from .plan_scoring import PlanScoring
from .tile_facts import facts_from
from .tile_report import TileReport

DERIVED = "derived"
REPORT = "report"


class TileReporter:
    """Answers what a tile has to say, for a named tile or the city's tile that came furthest."""

    def __init__(self, catalog: CityCatalog) -> None:
        self._catalog = catalog

    def report(self, text: str, tile_id: str) -> TileReport:
        return report_of(self._catalog.tile_paths(text, tile_id))

    def report_furthest(self, text: str) -> TileReport:
        """The report of the city's densest tile with physics, else with a baseline, else built."""
        furthest = self._catalog.furthest_tile(text)
        return report_of(self._catalog.tile_paths(text, furthest.id))


def report_of(paths: TilePaths) -> TileReport:
    """The report for a tile record, from the cache while its sources are unchanged."""
    store = FieldStore(paths)
    cache = DerivedCache(paths.root / DERIVED)
    sources = store.sources()
    if cache.current(REPORT, sources):
        return TileReport.model_validate(cache.read(REPORT))
    report = _compute(paths, store)
    cache.write(REPORT, report.model_dump(mode="json"), sources)
    return report


def _compute(paths: TilePaths, store: FieldStore) -> TileReport:
    stages = paths.stages()
    facts = facts_from(store.provenance(), str(paths.urban_centre))
    report = TileReport(
        city=facts.key, tile=paths.tile.id, name=facts.name, stages=stages, facts=facts
    )
    if not stages.baseline:
        return report
    scoring = PlanScoring(store)
    report = report.model_copy(
        update={
            "baseline": scoring.baseline(),
            "met": store.meteorology(),
            "hourly": _hourly(store),
        }
    )
    if not stages.physics:
        return report
    return report.model_copy(update={"plans": scoring.plans(), "physics": scoring.physics()})


def _hourly(store: FieldStore) -> list[HourlyStatistic]:
    """The median and maximum of every hour, or nothing when the engine's raster was cleaned up."""
    if not store.has_hourly():
        return []
    return [
        HourlyStatistic(
            hour=hour, median=round(float(np.median(band)), 1), max=round(float(band.max()), 1)
        )
        for hour, band in enumerate(store.hourly_temperature())
    ]
