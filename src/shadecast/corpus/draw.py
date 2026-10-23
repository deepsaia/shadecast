"""How a stratified sample of urban centres is drawn."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Draw:
    """k centres per Koppen and income stratum, above a population floor, from a seed."""

    per_stratum: int
    min_population_2025: int
    seed: int
