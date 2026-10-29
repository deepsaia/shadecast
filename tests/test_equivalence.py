"""One question asked of the service, the command line and the HTTP client is answered alike."""

import json

import pytest
from fastapi.testclient import TestClient
from support import synthetic_tile
from support.fixtures import fixture_centres
from support.fixtures import fixture_corpus
from support.fixtures import fixture_tiles
from typer.testing import CliRunner

from shadecast import cities
from shadecast import tile_cli
from shadecast.cli import app
from shadecast.corpus import tile_description
from shadecast.corpus import tile_paths
from shadecast.server.app import build_app
from shadecast.server.services import Services
from shadecast.server.settings import ServerSettings
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.findings_report import FindingsReport
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.results_report import ResultsReport
from shadecast.service.run_status import RunStatus
from shadecast.service.selection import Selection
from shadecast.service.tile_index import TileIndex
from shadecast.service.tile_reporter import TileReporter

runner = CliRunner()


@pytest.fixture
def everything(tmp_path, monkeypatch):
    tiles_root = tmp_path / "tiles"
    tile = synthetic_tile.write_bundle(tiles_root)
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setattr(cities, "corpus", fixture_corpus)
    monkeypatch.setattr(tile_cli, "load_centres", fixture_centres)
    monkeypatch.setattr(tile_description, "describe", fixture_tiles)
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tiles_root)
    monkeypatch.setattr(tile_paths, "MODELS_ROOT", tmp_path / "models")
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()),
        fixture_centres,
        TileIndex(tiles_root, fixture_tiles),
        ModelCatalog(tmp_path / "models"),
    )
    services = Services(
        catalog=catalog,
        reporter=TileReporter(catalog),
        results=ResultsReport(catalog, tmp_path),
        findings=FindingsReport(tmp_path),
        models=ModelCatalog(tmp_path / "models"),
        runs=RunStatus(catalog, tmp_path / "models"),
    )
    settings = ServerSettings(data_root=tmp_path, static_dir=tmp_path / "static")
    return services, TestClient(build_app(settings, services))


def test_a_city_s_tiles_agree_three_ways(everything):
    services, client = everything
    direct = [tile.model_dump(mode="json") for tile in services.catalog.tiles("ahmedabad")]
    command = runner.invoke(app, ["tile", "list", "ahmedabad", "--json"])
    assert command.exit_code == 0, command.output
    assert json.loads(command.stdout)["tiles"] == direct
    assert client.get("/api/v1/cities/ahmedabad/tiles").json() == direct


def test_a_tile_s_report_agrees_three_ways(everything):
    services, client = everything
    direct = services.reporter.report("ahmedabad", synthetic_tile.TILE_ID).model_dump(mode="json")
    command = runner.invoke(app, ["tile", "report", "ahmedabad", "--tile", synthetic_tile.TILE_ID, "--json"])
    assert command.exit_code == 0, command.output
    assert json.loads(command.stdout) == direct
    assert client.get(f"/api/v1/cities/ahmedabad/tiles/{synthetic_tile.TILE_ID}/report").json() == direct
