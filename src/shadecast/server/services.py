"""The question services the server answers from, built once when the app is created."""

from __future__ import annotations

from dataclasses import dataclass

from ..corpus.urban_centre import UrbanCentre
from ..corpus.urban_centres import UrbanCentres
from ..service.city_catalog import CityCatalog
from ..service.findings_report import FindingsReport
from ..service.missing_stage import MissingStage
from ..service.model_catalog import ModelCatalog
from ..service.results_report import ResultsReport
from ..service.run_status import RunStatus
from ..service.selection import Selection
from ..service.tile_index import TileIndex
from ..service.tile_reporter import TileReporter
from .settings import ServerSettings


@dataclass(frozen=True)
class Services:
    catalog: CityCatalog
    reporter: TileReporter
    results: ResultsReport
    findings: FindingsReport
    models: ModelCatalog
    runs: RunStatus

    @classmethod
    def open(cls, settings: ServerSettings) -> Services:
        """The services over the real selection and database and the settings' data root.

        The server regenerates nothing: a centre whose tiles were never described is answered
        with the command that describes them, never by fetching rasters on a request.
        """
        index = TileIndex(settings.tiles_root, _never_describe)
        catalog = CityCatalog(Selection.read(), UrbanCentres.load, index)
        return cls(
            catalog=catalog,
            reporter=TileReporter(catalog),
            results=ResultsReport(catalog, settings.data_root),
            findings=FindingsReport(settings.data_root),
            models=ModelCatalog(settings.tiles_root, settings.models_root),
            runs=RunStatus(catalog, settings.models_root),
        )


def _never_describe(centre: UrbanCentre) -> list[dict]:
    raise MissingStage("tiles file", centre.slug, f"sdc tile list {centre.slug}")
