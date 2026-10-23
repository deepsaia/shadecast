"""The CoolBench city corpus.

Stratified by Koppen climate zone and World Bank income group, with deliberate
over-sampling of tropical and Global South cities. The 2026 review that found
tropical cities to be only 9% of urban-heat mitigation studies is the reason
this is a design constraint rather than an afterthought.

The cities live in ``corpus.json`` beside this module, one object per city, so that
adding a city is a data change rather than a code change. This module loads and
validates that file.

`in_wri` marks cities that also appear in WRI's Cool Cities Lab. Those are the
cross-validation set: our independently built bundles should agree with their
published UTCI where the two overlap, and any disagreement is informative.

Coordinates are a search *seed*, not the study area. The actual AOI is chosen by
`aoi_selector.select` from population density, so nobody has to hand-tune a box and
the choice is reproducible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path

CORPUS_PATH = Path(__file__).with_name("corpus.json")


@dataclass(frozen=True)
class City:
    key: str
    name: str
    country: str
    lat: float
    lon: float
    koppen: str  # main Koppen-Geiger class
    income: str  # World Bank group: L, LM, UM, H
    region: str
    in_wri: bool = False
    note: str = ""

    @property
    def global_south(self) -> bool:
        return self.income in ("L", "LM", "UM")


def _city_from(entry: dict, path: Path) -> City:
    """Build one City from a JSON object, naming the file and the key on any defect."""
    known = {field.name for field in fields(City)}
    unknown = sorted(set(entry) - known)
    key = entry.get("key", "?")
    if unknown:
        raise ValueError(f"{path.name}: city {key!r} has unknown fields {unknown}")
    try:
        return City(**entry)
    except TypeError as exc:
        raise ValueError(f"{path.name}: city {key!r} is missing a required field") from exc


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, City]:
    """Read the corpus file and return its cities keyed by short key, in file order."""
    path = Path(path)
    entries: list[dict] = json.loads(path.read_text())
    corpus: dict[str, City] = {}
    for entry in entries:
        city = _city_from(entry, path)
        if city.key in corpus:
            raise ValueError(f"{path.name}: duplicate city key {city.key!r}")
        corpus[city.key] = city
    return corpus


CORPUS: dict[str, City] = load_corpus()


def summary() -> dict:
    n = len(CORPUS)
    south = sum(c.global_south for c in CORPUS.values())
    tropical = sum(c.koppen.startswith("A") for c in CORPUS.values())
    arid = sum(c.koppen.startswith("B") for c in CORPUS.values())
    return {
        "cities": n,
        "global_south": f"{south} ({south / n:.0%})",
        "tropical_A": f"{tropical} ({tropical / n:.0%})",
        "arid_B": f"{arid} ({arid / n:.0%})",
        "southern_hemisphere": sum(c.lat < 0 for c in CORPUS.values()),
        "wri_overlap": sum(c.in_wri for c in CORPUS.values()),
        "regions": len({c.region for c in CORPUS.values()}),
        "koppen_classes": len({c.koppen for c in CORPUS.values()}),
    }
