"""A city as it was laid out before tiles: a bundle directory and a surrogate directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..cities import City


@dataclass(frozen=True)
class LegacyCity:
    city: City
    bundle: Path  # out/corpus/<key> or data/cities/<key>
    surrogate: Path  # data/surrogate/<key>, which may not exist
