"""The selected cities: their keys and ids from the selection file, their records only when asked.

A key resolves to an urban centre id without the database, which is what every command that
only reads disk needs. The records, with names and strata, come from the database the first
time something asks for them.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from .. import cities
from ..cities import City
from ..corpus.urban_centres import UrbanCentres

LoadCentres = Callable[[], UrbanCentres]


class Selection:
    def __init__(self, entries: list[dict], load_cities: Callable[[LoadCentres], dict[str, City]]) -> None:
        self._entries = entries
        self._load_cities = load_cities

    @classmethod
    def read(cls) -> Selection:
        """The selection file beside the code; records resolve through the corpus when asked."""
        entries = cities.selection()
        return cls(entries, partial(_corpus, entries))

    @classmethod
    def resolved(cls, listed: dict[str, City]) -> Selection:
        """A selection whose records are already in hand, so no database is ever needed."""
        entries = [{"key": city.key, "ucdb_id": city.ucdb_id} for city in listed.values()]
        return cls(entries, partial(_given, listed))

    def keys(self) -> list[str]:
        return [str(entry.get("key")) for entry in self._entries]

    def ucdb_id(self, key: str) -> int | None:
        for entry in self._entries:
            if entry.get("key") == key:
                return int(str(entry.get("ucdb_id", 0)))
        return None

    def cities(self, load_centres: LoadCentres) -> dict[str, City]:
        """The records, loading the database only when the selection was read from its file."""
        return self._load_cities(load_centres)


def _corpus(entries: list[dict], load_centres: LoadCentres) -> dict[str, City]:
    return cities.corpus(entries, load_centres())


def _given(listed: dict[str, City], _load_centres: LoadCentres) -> dict[str, City]:
    return listed
