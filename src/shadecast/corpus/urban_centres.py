"""Every urban centre in the database, resolvable by id, slug or name.

Resolution is deliberately strict in one direction and forgiving in the other. An id or an exact
slug resolves at once. A name is matched without case, accents or punctuation against every
name the database knows for a centre, including its alias list. A fragment that fits several
centres is refused with the candidates listed, because silently picking one would build the
wrong city.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import ucdb
from .legend import income_code, is_missing, koppen_code, koppen_symbol
from .slugs import assign_slugs, slugify
from .urban_centre import UrbanCentre

NAME_SEPARATOR = ";"
CANDIDATES_SHOWN = 8


def _names(main: object, listed: object) -> tuple[str, ...]:
    """The main name first, then every alias the database lists, without repeats."""
    names: list[str] = []
    listed_text = "" if is_missing(listed) else str(listed)
    for name in [str(main), *listed_text.split(NAME_SEPARATOR)]:
        clean = name.strip()
        if clean and clean not in names:
            names.append(clean)
    return tuple(names)


def _centre_from(record: dict, slug: str) -> UrbanCentre:
    return UrbanCentre(
        id=int(record.get(ucdb.ID, 0)),
        name=str(record.get(ucdb.NAME, "")),
        names=_names(record.get(ucdb.NAME, ""), record.get(ucdb.NAMES)),
        slug=slug,
        country=str(record.get(ucdb.COUNTRY, "")),
        population=round(float(record.get(ucdb.POPULATION, 0.0))),
        area_km2=int(record.get(ucdb.AREA, 0)),
        income=income_code(record.get(ucdb.INCOME_GROUP)),
        koppen_code=koppen_code(record.get(ucdb.KOPPEN_CODE)),
        koppen=koppen_symbol(record.get(ucdb.KOPPEN_CODE)),
        lon=float(record.get(ucdb.LON, float("nan"))),
        lat=float(record.get(ucdb.LAT, float("nan"))),
    )


def _describe(centre: UrbanCentre) -> str:
    return f"{centre.slug} ({centre.country}, {centre.population:,} people)"


class UrbanCentres:
    """The corpus: every urban centre, in database order, with unique slugs."""

    def __init__(self, frame: pd.DataFrame) -> None:
        slugs = assign_slugs(frame)
        self._by_id: dict[int, UrbanCentre] = {}
        for record, slug in zip(frame.to_dict("records"), slugs, strict=True):
            centre = _centre_from(record, str(slug))
            self._by_id[centre.id] = centre
        self._by_slug: dict[str, UrbanCentre] = {c.slug: c for c in self._by_id.values()}

    @classmethod
    def load(cls, cache_dir: Path = ucdb.CACHE) -> UrbanCentres:
        """Read the corpus from the cached database, fetching it on first use."""
        return cls(ucdb.table(cache_dir))

    def __len__(self) -> int:
        return len(self._by_id)

    def all(self) -> list[UrbanCentre]:
        return list(self._by_id.values())

    def by_id(self, centre_id: int) -> UrbanCentre:
        centre = self._by_id.get(int(centre_id))
        if centre is None:
            raise KeyError(f"no urban centre with id {centre_id}")
        return centre

    def by_slug(self, slug: str) -> UrbanCentre | None:
        return self._by_slug.get(slug)

    def search(
        self, text: str, *, country: str | None = None, min_population: int = 0
    ) -> list[UrbanCentre]:
        """Centres whose names contain the text, most populous first."""
        key = slugify(text)
        country_key = slugify(country) if country else None
        found = [
            centre
            for centre in self._by_id.values()
            if (not key or any(key in slugify(name) for name in centre.names))
            and (country_key is None or slugify(centre.country) == country_key)
            and centre.population >= min_population
        ]
        return sorted(found, key=lambda centre: -centre.population)

    def resolve(self, text: str) -> UrbanCentre:
        """One centre from an id, a slug or a name; refuse anything ambiguous."""
        query = str(text).strip()
        if query.isdigit():
            return self.by_id(int(query))
        key = slugify(query)
        exact_slug = self.by_slug(query.lower()) or self.by_slug(key)
        if exact_slug is not None:
            return exact_slug
        exact_names = [
            centre
            for centre in self._by_id.values()
            if any(slugify(name) == key for name in centre.names)
        ]
        if len(exact_names) == 1:
            return exact_names[0]
        found = exact_names or self.search(query)
        if not found:
            raise ValueError(f"no urban centre matches {query!r}")
        if len(found) > 1:
            shown = ", ".join(_describe(centre) for centre in found[:CANDIDATES_SHOWN])
            raise ValueError(f"{query!r} matches {len(found)} urban centres: {shown}")
        return found[0]
