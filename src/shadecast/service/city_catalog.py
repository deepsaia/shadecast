"""What the selected cities are and what each of their tiles has reached, read from disk alone."""

from __future__ import annotations

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
    # database resolves any centre a command names, and the index knows the 1 km tiles.
    def __init__(self, selection: dict[str, City], centres: UrbanCentres, index: TileIndex) -> None:
        self._selection = selection
        self._centres = centres
        self._index = index

    @classmethod
    def open(cls, tiles_root: Path) -> CityCatalog:
        """The catalog over the real selection, the real database and a tiles root."""
        index = TileIndex(tiles_root, tile_description.describe)
        return cls(cities.corpus(), UrbanCentres.load(), index)

    def cities(self) -> list[CitySummary]:
        """Every selected city with how many of its tiles have reached each stage."""
        return [self._summary(city) for city in self._selection.values()]

    def city(self, text: str) -> CitySummary:
        """One selected city; an urban centre outside the selection is unknown here."""
        centre = self.centre(text)
        for city in self._selection.values():
            if city.ucdb_id == centre.id:
                return self._summary(city)
        raise UnknownCity(text, "it is an urban centre but not a selected city")

    def centre(self, text: str) -> UrbanCentre:
        """The urban centre a selection key, an id, a slug or a name refers to."""
        try:
            return self._resolve(str(text).strip())
        except (KeyError, ValueError) as exc:
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
        return self._location(self._paths(self.centre(text), tile_id))

    def tiles_on_disk(self, text: str) -> list[TileLocation]:
        """Every tile directory present for the centre, in id order, listed in the file or not."""
        centre = self.centre(text)
        found = TilePaths.existing(self._index.tiles_root, centre.id)
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
        centre = self.centre(text)
        return self._counts(centre.id, centre.tiles)

    def _resolve(self, query: str) -> UrbanCentre:
        selected = self._selection.get(query)
        if selected is not None:
            return self._centres.by_id(selected.ucdb_id)
        return self._centres.resolve(query)

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
        reached = [
            paths.stages() for paths in TilePaths.existing(self._index.tiles_root, urban_centre)
        ]
        return StageCounts(
            tiles=tiles,
            bundle=sum(stages.bundle for stages in reached),
            baseline=sum(stages.baseline for stages in reached),
            physics=sum(stages.physics for stages in reached),
            model=sum(stages.model for stages in reached),
            results=sum(stages.results for stages in reached),
        )

    def _summaries(self, centre: UrbanCentre, payload: dict) -> list[TileSummary]:
        rows = payload.get("tiles", [])
        return [
            TileSummary.model_validate(
                {**row, "stages": self._paths(centre, str(row.get("id"))).stages()}
            )
            for row in select_densest(rows, len(rows))
        ]

    def _paths(self, centre: UrbanCentre, tile_id: str) -> TilePaths:
        try:
            tile = Tile.from_id(tile_id)
        except ValueError as exc:
            raise UnknownTile(centre.slug, tile_id) from exc
        return TilePaths(self._index.tiles_root, centre.id, tile)

    def _location(self, paths: TilePaths) -> TileLocation:
        return TileLocation.model_validate({**paths.as_dict(), "stages": paths.stages()})
