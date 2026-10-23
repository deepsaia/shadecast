"""Short, unique, typeable names for urban centres.

The database names 11,422 centres and 284 names repeat, London and San Jose among them, while
113 names have no Latin letters at all. A slug is the lower-case ASCII letters and digits of the
name. The most populous namesake keeps the bare slug, the others carry their country, and any
that still collide carry their id, so every slug names exactly one centre and the common case
stays short.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

from . import ucdb

NOT_ALLOWED = re.compile(r"[^a-z0-9]+")


def slugify(text: object) -> str:
    """Lower-case ASCII letters and digits of a name; empty when the name has none."""
    ascii_text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return NOT_ALLOWED.sub("", ascii_text.lower())


def _candidates(base: str, country: str, centre_id: int) -> tuple[str, str, str]:
    country_slug = slugify(country)
    return base, f"{base}-{country_slug}", f"{base}-{country_slug}-{centre_id}"


def assign_slugs(frame: pd.DataFrame) -> pd.Series:
    """One unique slug per row of a corpus table, aligned to the frame's index."""
    by_population = frame.sort_values(ucdb.POPULATION, ascending=False)
    taken: set[str] = set()
    chosen: dict[int, str] = {}
    for record in by_population.to_dict("records"):
        centre_id = int(record.get(ucdb.ID, 0))
        base = slugify(record.get(ucdb.NAME, "")) or f"uc{centre_id}"
        country = str(record.get(ucdb.COUNTRY, ""))
        slug = next(
            option for option in _candidates(base, country, centre_id) if option not in taken
        )
        taken.add(slug)
        chosen[centre_id] = slug
    return pd.Series(
        [chosen.get(int(centre_id), "") for centre_id in frame[ucdb.ID]],
        index=frame.index,
        name="slug",
    )
