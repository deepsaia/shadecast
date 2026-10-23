"""The CoolBench city corpus: a selection of urban centres from GHS-UCDB.

The database is the corpus; the benchmark reports on a selection. ``corpus.json`` beside this
module lists the selected urban centres by database id with the only fields the database
cannot know: our short key, our regional grouping, whether WRI's Cool Cities Lab also covers
the city, and a note. Every stratum (Koppen class, income group, country, 2025 population, and the
centroid that seeds the tile search) is read from the database, so nothing here is typed from
memory.

The selection is stratified by Koppen climate zone and World Bank income group, with deliberate
over-sampling of tropical and Global South cities. The 2026 review that found tropical cities
to be only 9% of urban-heat mitigation studies is the reason this is a design constraint rather
than an afterthought.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .corpus import ucdb
from .corpus.urban_centres import UrbanCentres

SELECTION_PATH = Path(__file__).with_name("corpus.json")
SELECTION_FIELDS: dict[str, type] = {
    "ucdb_id": int,
    "key": str,
    "region": str,
    "in_wri": bool,
    "note": str,
}
REQUIRED_FIELDS = ("ucdb_id", "key", "region")
GLOBAL_SOUTH_INCOMES = ("L", "LM", "UM")


@dataclass(frozen=True)
class City:
    key: str
    ucdb_id: int
    name: str
    country: str
    lat: float
    lon: float
    koppen: str | None  # Koppen-Geiger class of the majority of the urban centre, or None
    income: str | None  # World Bank group: L, LM, UM, H, or None
    region: str
    population_2025: int
    tiles: int  # 1 km GHS cells inside the urban centre, which is its area in km2
    in_wri: bool = False
    note: str = ""

    @property
    def global_south(self) -> bool:
        return self.income in GLOBAL_SOUTH_INCOMES


def _check_entry(entry: dict, path: Path) -> None:
    key = entry.get("key", "?")
    unknown = sorted(set(entry) - set(SELECTION_FIELDS))
    if unknown:
        raise ValueError(
            f"{path.name}: city {key!r} has fields that belong to the database, not here: {unknown}"
        )
    missing = [name for name in REQUIRED_FIELDS if name not in entry]
    if missing:
        raise ValueError(f"{path.name}: city {key!r} lacks {missing}")
    for name, kind in SELECTION_FIELDS.items():
        value = entry.get(name)
        if value is not None and not isinstance(value, kind):
            raise ValueError(f"{path.name}: city {key!r} field {name!r} must be {kind.__name__}")


def selection(path: Path = SELECTION_PATH) -> list[dict]:
    """Read the selection file and refuse anything that is not an id plus our own fields."""
    path = Path(path)
    entries: list[dict] = json.loads(path.read_text())
    seen_keys: set[str] = set()
    seen_ids: set[int] = set()
    for entry in entries:
        _check_entry(entry, path)
        key = str(entry.get("key"))
        ucdb_id = int(entry.get("ucdb_id", 0))
        if key in seen_keys or ucdb_id in seen_ids:
            raise ValueError(f"{path.name}: duplicate city {key!r} ({ucdb_id})")
        seen_keys.add(key)
        seen_ids.add(ucdb_id)
    return entries


def urban_centres(cache_dir: Path = ucdb.CACHE) -> UrbanCentres:
    """The database, fetched on first use and read from the cache after that."""
    return UrbanCentres.load(cache_dir)


def _city(entry: dict, centres: UrbanCentres) -> City:
    key = str(entry.get("key"))
    ucdb_id = int(entry.get("ucdb_id", 0))
    try:
        centre = centres.by_id(ucdb_id)
    except KeyError as exc:
        raise KeyError(f"city {key!r}: the database has no urban centre {ucdb_id}") from exc
    return City(
        key=key,
        ucdb_id=centre.id,
        name=centre.name,
        country=centre.country,
        lat=centre.lat,
        lon=centre.lon,
        koppen=centre.koppen,
        income=centre.income,
        region=str(entry.get("region")),
        population_2025=centre.population_2025,
        tiles=centre.tiles,
        in_wri=bool(entry.get("in_wri", False)),
        note=str(entry.get("note", "")),
    )


def corpus(
    entries: list[dict] | None = None, centres: UrbanCentres | None = None
) -> dict[str, City]:
    """The selected cities keyed by short key, in selection order."""
    chosen = entries if entries is not None else selection()
    database = centres if centres is not None else urban_centres()
    return {str(entry.get("key")): _city(entry, database) for entry in chosen}


def summary(cities: Iterable[City]) -> dict:
    listed = list(cities)
    n = len(listed)
    south = sum(c.global_south for c in listed)
    tropical = sum((c.koppen or "").startswith("A") for c in listed)
    arid = sum((c.koppen or "").startswith("B") for c in listed)
    return {
        "cities": n,
        "global_south": f"{south} ({south / n:.0%})",
        "tropical_A": f"{tropical} ({tropical / n:.0%})",
        "arid_B": f"{arid} ({arid / n:.0%})",
        "southern_hemisphere": sum(c.lat < 0 for c in listed),
        "wri_overlap": sum(c.in_wri for c in listed),
        "regions": len({c.region for c in listed}),
        "koppen_classes": len({c.koppen for c in listed if c.koppen}),
    }
