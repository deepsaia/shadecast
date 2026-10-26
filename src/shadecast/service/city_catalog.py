"""What the selected cities are and what each of their tiles has reached, read from disk alone."""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from pathlib import Path

from .. import cities
from ..cities import City
from ..corpus import tile_description
from ..corpus.statistics import tile_stats
from ..corpus.tile import Tile
from ..corpus.tile_paths import TilePaths
from ..corpus.tiling import select_densest
from ..corpus.urban_centre import UrbanCentre
from ..corpus.urban_centres import UrbanCentres
from .city_summary import CitySummary
from .stage_counting import count_stages
from .stage_counts import StageCounts
from .tile_index import TileIndex
from .tile_location import TileLocation
from .tile_statistics import TileStatistics
from .tile_summary import TileSummary
from .unknown_city import UnknownCity
from .unknown_tile import UnknownTile


class CityCatalog:
    """Answers which cities are selected and what each of their tiles has on disk.

    A question service: it reads the selection, the urban centre database and the tile
    directories, and writes nothing except the tiles file when a centre is described for the
    first time. Stages come from the files that prove them, never from a record kept apart.
    """

    # Three collaborators because three records are read: the selection names the cities, the
    # database resolves any centre a command names, and the index knows the 1 km tiles. The
    # database is loaded only when a slug or a name must be resolved or a centre described, so
    # listing the selection and reading what is on disk stay fast and offline.
    def __init__(
        self,
        selection: dict[str, City],
        load_centres: Callable[[], UrbanCentres],
        index: TileIndex,
    ) -> None:
        self._selection = selection
        self._load_centres = load_centres
        self._index = index

    @classmethod
    def open(cls, tiles_root: Path) -> CityCatalog:
        """The catalog over the real selection, the real database and a tiles root."""
        index = TileIndex(tiles_root, tile_description.describe)
        return cls(cities.corpus(), UrbanCentres.load, index)

    @cached_property
    def _centres(self) -> UrbanCentres:
        return self._load_centres()

    def cities(self) -> list[CitySummary]:
        """Every selected city with how many of its tiles have reached each stage."""
        return [self._summary(city) for city in self._selection.values()]

    def city(self, text: str) -> CitySummary:
        """One selected city; an urban centre outside the selection is unknown here."""
        urban_centre = self.urban_centre_id(text)
        for city in self._selection.values():
            if city.ucdb_id == urban_centre:
                return self._summary(city)
        raise UnknownCity(text, "it is an urban centre but not a selected city")

    def urban_centre_id(self, text: str) -> int:
        """The id a key, an id, a slug or a name refers to; keys and ids need no database."""
        try:
            return self._resolve_id(str(text).strip())
        except (KeyError, ValueError) as exc:
            raise UnknownCity(text, str(exc)) from exc

    def centre(self, text: str) -> UrbanCentre:
        """The urban centre record a key, an id, a slug or a name refers to."""
        urban_centre = self.urban_centre_id(text)
        try:
            return self._centres.by_id(urban_centre)
        except KeyError as exc:
            raise UnknownCity(text, str(exc)) from exc

    def tiles(self, text: str) -> list[TileSummary]:
        """Every 1 km tile of the centre, densest first, with the stages each has reached."""
        centre = self.centre(text)
        return self._summaries(centre, self._index.read_or_describe(centre))

    def refresh(self, text: str) -> list[TileSummary]:
        """Describe the centre's tiles again, then list them as `tiles` does."""
        centre = self.centre(text)
        return self._summaries(centre, self._index.describe_and_write(centre))

    def tile(self, text: str, tile_id: str) -> TileLocation:
        """Where everything for one tile lives and which stages have run."""
        return self._location(self._paths(self.urban_centre_id(text), tile_id))

    def tiles_on_disk(self, text: str) -> list[TileLocation]:
        """Every tile directory present for the centre, in id order, listed in the file or not."""
        found = TilePaths.existing(self._index.tiles_root, self.urban_centre_id(text))
        return [self._location(paths) for paths in found]

    def statistics(self, text: str) -> TileStatistics:
        """Counts, people and spreads over the centre's tiles, with the stage counts."""
        centre = self.centre(text)
        rows = self._index.read_or_describe(centre).get("tiles", [])
        return TileStatistics(
            urban_centre=centre.id,
            name=centre.name,
            population_2025=centre.population_2025,
            area_km2=centre.area_km2,
            stages=self._counts(centre.id, centre.tiles),
            **tile_stats(rows),
        )

    def stage_counts(self, text: str) -> StageCounts:
        """How many of the centre's tiles have reached each stage, out of all it has."""
        urban_centre = self.urban_centre_id(text)
        return self._counts(urban_centre, self._tile_count(text, urban_centre))

    def _resolve_id(self, query: str) -> int:
        selected = self._selection.get(query)
        if selected is not None:
            return selected.ucdb_id
        if query.isdigit():
            return int(query)
        return self._centres.resolve(query).id

    def _tile_count(self, text: str, urban_centre: int) -> int:
        for city in self._selection.values():
            if city.ucdb_id == urban_centre:
                return city.tiles
        try:
            return self._centres.by_id(urban_centre).tiles
        except KeyError as exc:
            raise UnknownCity(text, str(exc)) from exc

    def _summary(self, city: City) -> CitySummary:
        return CitySummary(
            key=city.key,
            ucdb_id=city.ucdb_id,
            name=city.name,
            country=city.country,
            region=city.region,
            koppen=city.koppen,
            income=city.income,
            population_2025=city.population_2025,
            in_wri=city.in_wri,
            stages=self._counts(city.ucdb_id, city.tiles),
        )

    def _counts(self, urban_centre: int, tiles: int) -> StageCounts:
        return count_stages(self._index.tiles_root, urban_centre, tiles)

    def _summaries(self, centre: UrbanCentre, payload: dict) -> list[TileSummary]:
        rows = payload.get("tiles", [])
        return [
            TileSummary.model_validate(
                {**row, "stages": self._paths(centre.id, str(row.get("id"))).stages()}
            )
            for row in select_densest(rows, len(rows))
        ]

    def _paths(self, urban_centre: int, tile_id: str) -> TilePaths:
        try:
            tile = Tile.from_id(tile_id)
        except ValueError as exc:
            raise UnknownTile(str(urban_centre), tile_id) from exc
        return TilePaths(self._index.tiles_root, urban_centre, tile)

    def _location(self, paths: TilePaths) -> TileLocation:
        return TileLocation.model_validate({**paths.as_dict(), "stages": paths.stages()})
