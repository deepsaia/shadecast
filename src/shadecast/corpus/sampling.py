"""Draw a stratified benchmark set from the corpus.

A stratum is a Koppen class paired with a World Bank income group. Drawing k centres per stratum
above a population floor with a fixed seed makes the benchmark set a reproducible command rather
than a judgement call, and makes the stratification table something anyone can regenerate.
Centres missing either stratum are left out, because an unknown stratum cannot be sampled from.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from .urban_centre import UrbanCentre

Stratum = tuple[str, str]


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


def sample(
    centres: Iterable[UrbanCentre], *, per_stratum: int, min_population: int, seed: int
) -> list[UrbanCentre]:
    """Up to `per_stratum` centres from every stratum, ordered by stratum then population."""
    groups: dict[Stratum, list[UrbanCentre]] = {}
    for centre in centres:
        key = stratum(centre)
        if key is not None and centre.population_2025 >= min_population:
            groups.setdefault(key, []).append(centre)

    rng = np.random.default_rng(seed)
    drawn: list[UrbanCentre] = []
    for key in sorted(groups):
        members = groups.get(key, [])
        take = min(per_stratum, len(members))
        picked = rng.choice(len(members), size=take, replace=False)
        chosen = [members[int(index)] for index in picked]
        drawn.extend(sorted(chosen, key=lambda centre: -centre.population_2025))
    return drawn
