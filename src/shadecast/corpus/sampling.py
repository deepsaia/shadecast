"""Draw a stratified city selection from the corpus.

A stratum is a Koppen class paired with a World Bank income group. Drawing k centres per stratum
above a population floor with a fixed seed makes the selection a reproducible command rather
than a judgement call, and makes the stratification table something anyone can regenerate.
Centres missing either stratum are left out, because an unknown stratum cannot be sampled from.
"""

from __future__ import annotations

from collections.abc import Iterable
from operator import attrgetter

import numpy as np

from .draw import Draw
from .urban_centre import UrbanCentre

Stratum = tuple[str, str]
BY_POPULATION = attrgetter("population_2025")


def stratum(centre: UrbanCentre) -> Stratum | None:
    if centre.koppen is None or centre.income is None:
        return None
    return centre.koppen, centre.income


def strata(centres: Iterable[UrbanCentre]) -> dict[Stratum, int]:
    """How many centres fall in each stratum, in sorted stratum order."""
    counts: dict[Stratum, int] = {}
    for centre in centres:
        key = stratum(centre)
        if key is not None:
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _eligible(centres: Iterable[UrbanCentre], draw: Draw) -> dict[Stratum, list[UrbanCentre]]:
    groups: dict[Stratum, list[UrbanCentre]] = {}
    for centre in centres:
        key = stratum(centre)
        if key is not None and centre.population_2025 >= draw.min_population_2025:
            groups.setdefault(key, []).append(centre)
    return groups


def sample(centres: Iterable[UrbanCentre], draw: Draw) -> list[UrbanCentre]:
    """Up to `draw.per_stratum` centres from every stratum, by stratum then population."""
    groups = _eligible(centres, draw)
    rng = np.random.default_rng(draw.seed)
    drawn: list[UrbanCentre] = []
    for key in sorted(groups):
        members = groups.get(key, [])
        picked = rng.choice(len(members), size=min(draw.per_stratum, len(members)), replace=False)
        chosen = [members[int(index)] for index in picked]
        drawn.extend(sorted(chosen, key=BY_POPULATION, reverse=True))
    return drawn
