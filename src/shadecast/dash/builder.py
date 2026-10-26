"""Build the static bundle the walkthrough serves.

Everything the browser needs is precomputed to disk: one JSON index plus a handful of grayscale
atlases. The numbers come from the tile report service; this module packs them beside the
atlases it draws from the same arrays, so the page and `sdc tile report` cannot disagree.

Fields ship as data rather than as pictures. See `encode`: the color ramp is applied in the
browser, which is what lets a visitor hover a pixel and read its temperature, scrub the day
without a network round trip, and download one file instead of twenty four.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from .. import sources
from ..corpus.tile_paths import TilePaths
from ..service.field_store import FieldStore
from ..service.findings_report import FindingsReport
from ..service.plan import Plan
from ..service.results_report import results_from
from ..service.tile_report import TileReport
from ..service.tile_reporter import report_of
from . import encode

logger = logging.getLogger(__name__)

TILE_PX = 384
# The plan maps are shown at roughly 550 px, so 320 was a visible upscale. Placement is
# a binary mask and compresses to almost nothing at high resolution; the cooling field is
# continuous and is what actually costs bytes, so it takes the middle size.
PLACE_PX = 576
COOL_PX = 512


class AtlasWriter:
    """Packs one tile's fields into the grayscale sheets the walkthrough draws, named by city."""

    def __init__(self, out_dir: Path, city: str) -> None:
        self._out_dir = Path(out_dir)
        self._city = city

    def hours(self, store: FieldStore, report: TileReport) -> dict:
        """Every hour of the design day in one sheet, on one shared scale.

        One scale across the whole day is deliberate. Rescaling each hour to its own range
        would hide the very thing the animation exists to show, which is that the city heats
        and cools while the shade pattern sweeps across it.
        """
        if not store.has_hourly():
            return {}
        bands = list(store.hourly_temperature())
        meta = encode.atlas(bands, self._sheet("hours"), size=TILE_PX, columns=6)
        meta["hours"] = [statistic.model_dump() for statistic in report.hourly]
        return meta

    def context(self, store: FieldStore) -> dict:
        return encode.atlas([store.heights()], self._sheet("ctx"), size=TILE_PX, columns=1)

    def plans(self, store: FieldStore, plans: list[Plan]) -> dict:
        """Every plan's cooling and placement in two sheets, slot by slot in report order."""
        entries, cooling, placement = [], [], []
        for slot, plan in enumerate(plans):
            placed, response = store.response(plan.id)
            entries.append({**plan.model_dump(), "tile": slot})
            cooling.append(response)
            placement.append(placed.astype(np.float32))
        return {
            "list": entries,
            "cooling": encode.atlas(cooling, self._sheet("cool"), size=COOL_PX, columns=5),
            "placement": encode.atlas(placement, self._sheet("place"), size=PLACE_PX, columns=5),
        }

    def _sheet(self, name: str) -> Path:
        return self._out_dir / f"{self._city}_{name}.png"


def build_city(city: str, tile_root: Path, out_dir: Path) -> dict:
    """Assemble one city's payload: the tile report plus the atlases drawn from the same arrays."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = TilePaths.of_root(Path(tile_root))
    report = report_of(paths)
    store = FieldStore(paths)
    atlases = AtlasWriter(out_dir, city)
    hours = atlases.hours(store, report) if report.baseline is not None else {}
    logger.info("%s: %d hourly frames", city, hours.get("count", 0))
    return {
        "city": city,
        "name": report.name,
        "provenance": report.facts.model_dump(),
        "baseline": report.baseline.model_dump() if report.baseline is not None else {},
        "met": [hour.model_dump() for hour in report.met],
        "hours": hours,
        "context": atlases.context(store),
        "plans": atlases.plans(store, report.plans),
        "physics": report.physics.model_dump() if report.physics is not None else {},
    }


def build_index(cities: list[tuple[str, Path]], out_dir: Path, data_root: Path) -> dict:
    """Build every city plus the findings panel, and write index.json and results.json."""
    out_dir = Path(out_dir)
    payload = {
        "cities": [build_city(key, tile_root, out_dir) for key, tile_root in cities],
        "findings": FindingsReport(data_root).collect().model_dump(),
        "references": sources.grouped(),
    }
    (out_dir / "index.json").write_text(json.dumps(payload, separators=(",", ":")))
    logger.info("index.json written with %d cities", len(payload["cities"]))

    # The second read of each report comes from the derived cache the first one wrote.
    reports = [report_of(TilePaths.of_root(Path(tile_root))) for _, tile_root in cities]
    measured = results_from(reports, data_root)
    (out_dir / "results.json").write_text(measured.model_dump_json())
    logger.info("results.json written with %d plans", measured.totals.plans)
    return payload
