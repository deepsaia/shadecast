"""One urban centre as the corpus sees it."""

from __future__ import annotations

from dataclasses import dataclass

GLOBAL_SOUTH_INCOMES = ("L", "LM", "UM")


@dataclass(frozen=True)
class UrbanCentre:
    """An urban centre from GHS-UCDB with the strata the benchmark is reported on.

    `area_km2` doubles as the number of 1 km tiles, because every urban centre boundary is an
    exact union of 1 km cells of the GHS grid. Missing strata are None, never a guess.
    """

    id: int
    name: str
    names: tuple[str, ...]
    slug: str
    country: str
    population_2025: int  # the GHS-POP 2025 epoch, as GHS-UCDB reports it
    area_km2: int
    income: str | None
    koppen_code: int | None
    koppen: str | None
    lon: float
    lat: float

    @property
    def tiles(self) -> int:
        return self.area_km2

    @property
    def global_south(self) -> bool:
        return self.income in GLOBAL_SOUTH_INCOMES
