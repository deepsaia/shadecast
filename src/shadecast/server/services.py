"""The question services the server answers from, built once when the app is created."""

from __future__ import annotations

from dataclasses import dataclass

from ..service.city_catalog import CityCatalog
from ..service.findings_report import FindingsReport
from ..service.model_catalog import ModelCatalog
from ..service.results_report import ResultsReport
from ..service.run_status import RunStatus
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
        """The services over the real selection and database and the settings' data root."""
        catalog = CityCatalog.open(settings.tiles_root)
        return cls(
            catalog=catalog,
            reporter=TileReporter(catalog),
            results=ResultsReport(catalog, settings.data_root),
            findings=FindingsReport(settings.data_root),
            models=ModelCatalog(settings.tiles_root, settings.models_root),
            runs=RunStatus(catalog, settings.models_root),
        )
