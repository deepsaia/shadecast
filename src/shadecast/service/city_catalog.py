"""What the selected cities are and what each of their tiles has reached, read from disk alone."""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from functools import partial
from pathlib import Path

from ..cities import City
from ..corpus import tile_description
from ..corpus.statistics import tile_stats
from ..corpus.tile import Tile
from ..corpus.tile_paths import TilePaths
from ..corpus.tile_stages import TileStages
from ..corpus.tiling import select_densest
from ..corpus.urban_centre import UrbanCentre
from ..corpus.urban_centres import UrbanCentres
from .city_summary import CitySummary
from .missing_stage import MissingStage
from .model_catalog import ModelCatalog
from .selection import Selection
from .stage_counting import count_stages
from .stage_counts import StageCounts
from .tile_grid import TileGrid
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

    # Four collaborators because four records are read: the selection names the cities, the
    # database resolves any centre a command names, the index knows the 1 km tiles, and the model
    # catalog knows which tiles a model learned from, since models live apart from their tiles.
    # The database is loaded only when a slug or a name must be resolved or a centre described,
    # so listing the selection and reading what is on disk stay fast and offline.
    def __init__(
        self,
        selection: Selection,
        load_centres: Callable[[], UrbanCentres],
        index: TileIndex,
        models: ModelCatalog,
    ) -> None:
        self._selection = selection
        self._load_centres = load_centres
        self._index = index
        self._models = models

    @classmethod
    def open(cls, tiles_root: Path, models_root: Path) -> CityCatalog:
        """The catalog over the real selection, the real database and the two data roots."""
        index = TileIndex(tiles_root, tile_description.describe)
        return cls(Selection.read(), UrbanCentres.load, index, ModelCatalog(models_root))

    @classmethod
    def with_centres(cls, centres: UrbanCentres, tiles_root: Path, models_root: Path) -> CityCatalog:
        """The catalog over the real selection and a database a command has already loaded."""
        index = TileIndex(tiles_root, tile_description.describe)
        return cls(Selection.read(), partial(_loaded, centres), index, ModelCatalog(models_root))

    @classmethod
    def over(cls, listed: dict[str, City], tiles_root: Path, models_root: Path) -> CityCatalog:
        """The catalog over city records already in hand, the real database and the data roots."""
        index = TileIndex(tiles_root, tile_description.describe)
        return cls(Selection.resolved(listed), UrbanCentres.load, index, ModelCatalog(models_root))

    @cached_property
    def _centres(self) -> UrbanCentres:
        return self._load_centres()

    @cached_property
    def _records(self) -> dict[str, City]:
        return self._selection.cities(self._load_centres)

    def keys(self) -> list[str]:
        """The selection keys, without loading anything."""
        return self._selection.keys()

    def records(self) -> dict[str, City]:
        """The selected cities' records, keyed by selection key; loads the database when needed."""
        return self._records

    def tile_rows(self, text: str) -> list[dict]:
        """The centre's described tiles as the tiles file holds them, described first if needed."""
        return self._index.read_or_describe(self.centre(text)).get("tiles", [])

    def cities(self) -> list[CitySummary]:
        """Every selected city with how many of its tiles have reached each stage."""
        return [self._summary(city) for city in self._records.values()]

    def city(self, text: str) -> CitySummary:
        """One selected city; an urban centre outside the selection is unknown here."""
        urban_centre = self.urban_centre_id(text)
        for city in self._records.values():
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

    def grid(self, text: str) -> TileGrid:
        """The centre's tiles as a grid for a map, each flagged when a model learned from it."""
        centre = self.centre(text)
        rows = self._index.read_or_describe(centre).get("tiles", [])
        return TileGrid.of(rows, self._models.tiles_with_models(centre.id))

    def refresh(self, text: str) -> list[TileSummary]:
        """Describe the centre's tiles again, then list them as `tiles` does."""
        centre = self.centre(text)
        return self._summaries(centre, self._index.describe_and_write(centre))

    def densest_built(self, text: str) -> TilePaths:
        """The record of the city's densest built tile; nothing built names the build command."""
        built = [tile for tile in self.ranked_on_disk(text) if tile.stages.bundle]
        if not built:
            raise MissingStage("bundle", text, f"sdc build {text}")
        return self.tile_paths(text, built[0].tile)

    def tiles_file(self, text: str) -> Path:
        """Where the centre's tiles are described on disk."""
        return self._index.path(self.centre(text))

    def tile(self, text: str, tile_id: str) -> TileLocation:
        """Where everything for one tile lives and which stages have run."""
        paths = self.tile_paths(text, tile_id)
        return self._location(paths, self._models.tiles_with_models(paths.urban_centre))

    def tile_paths(self, text: str, tile_id: str) -> TilePaths:
        """The on-disk record of one tile, for services that read its files."""
        return self._paths(self.urban_centre_id(text), tile_id)

    def furthest_tile(self, text: str) -> TileLocation:
        """The densest tile that came furthest: with physics, else with a baseline, else built.

        Read from disk alone, ranked by the tiles file when there is one, so it needs no database
        and no description.
        """
        tiles = self.ranked_on_disk(text)
        for reached in ("physics", "baseline", "bundle"):
            candidates = [tile for tile in tiles if tile.stages.model_dump().get(reached)]
            if candidates:
                return candidates[0]
        raise MissingStage("bundle", text, f"sdc build {text}")

    def tiles_on_disk(self, text: str) -> list[TileLocation]:
        """Every tile directory present for the centre, in id order, listed in the file or not."""
        urban_centre = self.urban_centre_id(text)
        modelled = self._models.tiles_with_models(urban_centre)
        found = TilePaths.existing(self._index.tiles_root, urban_centre)
        return [self._location(paths, modelled) for paths in found]

    def ranked_on_disk(self, text: str) -> list[TileLocation]:
        """The tiles present, densest first by the tiles file when it exists; no database needed."""
        urban_centre = self.urban_centre_id(text)
        rows = self._index.rows_if_present(urban_centre)
        ranked = {str(row.get("id")): index for index, row in enumerate(select_densest(rows, len(rows)))}
        modelled = self._models.tiles_with_models(urban_centre)
        found = [self._location(paths, modelled) for paths in TilePaths.existing(self._index.tiles_root, urban_centre)]
        return sorted(found, key=partial(_rank_then_id, ranked))

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

    def stage_counts_of(self, centre: UrbanCentre) -> StageCounts:
        """The same for a centre record in hand, selected or not, without the selection."""
        return self._counts(centre.id, centre.tiles)

    def _resolve_id(self, query: str) -> int:
        selected = self._selection.ucdb_id(query)
        if selected is not None:
            return selected
        if query.isdigit():
            return int(query)
        return self._centres.resolve(query).id

    def _tile_count(self, text: str, urban_centre: int) -> int:
        if urban_centre in {city.ucdb_id for city in self._records.values()}:
            return next(c.tiles for c in self._records.values() if c.ucdb_id == urban_centre)
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
        return count_stages(self._stages_on_disk(urban_centre), tiles)

    def _stages_on_disk(self, urban_centre: int) -> list[TileStages]:
        modelled = self._models.tiles_with_models(urban_centre)
        return [
            paths.stages().with_model(paths.tile.id in modelled)
            for paths in TilePaths.existing(self._index.tiles_root, urban_centre)
        ]

    def _summaries(self, centre: UrbanCentre, payload: dict) -> list[TileSummary]:
        rows = payload.get("tiles", [])
        modelled = self._models.tiles_with_models(centre.id)
        return [
            TileSummary.model_validate({**row, "stages": self._stages_of(centre.id, str(row.get("id")), modelled)})
            for row in select_densest(rows, len(rows))
        ]

    # Three arguments: the tile is named by centre and id, and the modelled tiles are read from
    # the models root once per listing rather than once per row.
    def _stages_of(self, urban_centre: int, tile_id: str, modelled: set[str]) -> TileStages:
        """The stages of a listed tile; a row whose id is not a tile id has none on disk.

        Older files listed tiles under a scheme the layout no longer uses.
        """
        try:
            tile = Tile.from_id(tile_id)
        except ValueError:
            return TileStages()
        stages = TilePaths(self._index.tiles_root, urban_centre, tile).stages()
        return stages.with_model(tile_id in modelled)

    def _paths(self, urban_centre: int, tile_id: str) -> TilePaths:
        try:
            tile = Tile.from_id(tile_id)
        except ValueError as exc:
            raise UnknownTile(str(urban_centre), tile_id) from exc
        return TilePaths(self._index.tiles_root, urban_centre, tile)

    def _location(self, paths: TilePaths, modelled: set[str]) -> TileLocation:
        stages = paths.stages().with_model(paths.tile.id in modelled)
        return TileLocation.model_validate({**paths.as_dict(), "stages": stages})


def _loaded(centres: UrbanCentres) -> UrbanCentres:
    return centres


def _rank_then_id(ranked: dict[str, int], tile: TileLocation) -> tuple[int, str]:
    return (ranked.get(tile.tile, len(ranked)), tile.tile)
