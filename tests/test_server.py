"""The server answers every question the CLI does, from the same services, as JSON under /api/v1."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from support import synthetic_tile
from support.fixtures import fixture_centres
from support.fixtures import fixture_corpus
from support.fixtures import fixture_tiles

from shadecast.server.app import build_app
from shadecast.server.services import Services
from shadecast.server.settings import ServerSettings
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.findings_report import FindingsReport
from shadecast.service.missing_stage import MissingStage
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.results_report import ResultsReport
from shadecast.service.run_status import RunStatus
from shadecast.service.scenario_service import ScenarioService
from shadecast.service.selection import Selection
from shadecast.service.sweep_service import SweepService
from shadecast.service.tile_index import TileIndex
from shadecast.service.tile_reporter import TileReporter


def _services(data_root: Path) -> Services:
    tiles_root = data_root / "tiles"
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()),
        fixture_centres,
        TileIndex(tiles_root, fixture_tiles),
        ModelCatalog(data_root / "models"),
    )
    scenarios = ScenarioService(catalog, ModelCatalog(data_root / "models"))

    return Services(
        catalog=catalog,
        reporter=TileReporter(catalog),
        results=ResultsReport(catalog, data_root),
        findings=FindingsReport(data_root),
        models=ModelCatalog(data_root / "models"),
        runs=RunStatus(catalog, data_root / "models"),
        scenarios=scenarios,
        sweeps=SweepService(scenarios),
    )


@pytest.fixture
def data_root(tmp_path) -> Path:
    root = tmp_path / "data"
    tile = synthetic_tile.write_bundle(root / "tiles")
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    return root


@pytest.fixture
def client(tmp_path, data_root) -> TestClient:
    settings = ServerSettings(data_root=data_root, static_dir=tmp_path / "static")
    return TestClient(build_app(settings, _services(data_root)))


def test_health_says_alive_and_ready_with_the_selection_size(client, data_root):
    payload = client.get("/api/v1/health").json()
    assert payload["ready"] is True and payload["cities"] == 2 and payload["version"]
    assert "data_root" not in payload


def test_health_is_not_ready_without_a_data_root(tmp_path):
    settings = ServerSettings(data_root=tmp_path / "nowhere", static_dir=tmp_path / "static")
    client = TestClient(build_app(settings, _services(tmp_path / "nowhere")))
    assert client.get("/api/v1/health").json()["ready"] is False


def test_cities_and_one_city_s_statistics(client):
    cities = client.get("/api/v1/cities").json()
    assert [city["key"] for city in cities] == ["ahmedabad", "london"]
    assert cities[0]["stages"]["bundle"] == 1
    statistics = client.get("/api/v1/cities/ahmedabad").json()
    assert statistics["tiles"] == len(fixture_tiles()) and statistics["stages"]["physics"] == 1


def test_tiles_a_tile_and_its_report(client):
    tiles = client.get("/api/v1/cities/ahmedabad/tiles").json()
    assert tiles[0]["id"] == synthetic_tile.TILE_ID and tiles[0]["stages"]["physics"] is True
    grid = client.get("/api/v1/cities/ahmedabad/grid").json()
    basemap = client.get("/api/v1/basemap").json()
    assert basemap["source"] == "openfreemap" and basemap["style_url"].startswith("https://tiles.openfreemap.org/")
    assert grid["columns"][0] == "west" and len(grid["ids"]) == len(fixture_tiles()) == grid["described"]
    location = client.get(f"/api/v1/cities/ahmedabad/tiles/{synthetic_tile.TILE_ID}").json()
    assert location["tile"] == synthetic_tile.TILE_ID and location["stages"]["bundle"] is True
    report = client.get(f"/api/v1/cities/ahmedabad/tiles/{synthetic_tile.TILE_ID}/report").json()
    assert [plan["arrangement"] for plan in report["plans"]] == [
        "clustered",
        "corridor",
        "scattered",
    ]
    furthest = client.get("/api/v1/cities/ahmedabad/report").json()
    assert furthest["tile"] == synthetic_tile.TILE_ID and furthest["physics"]["designs"] == 4


def test_failures_name_what_is_missing(client):
    unknown = client.get("/api/v1/cities/atlantis/tiles")
    assert unknown.status_code == 404 and unknown.json()["kind"] == "UnknownCity"
    assert "atlantis" in unknown.json()["error"]
    nothing_built = client.get("/api/v1/cities/london/report")
    assert nothing_built.status_code == 404
    assert nothing_built.json()["kind"] == "MissingStage"
    assert nothing_built.json()["command"] == "sdc build london"
    malformed = client.get("/api/v1/cities/ahmedabad/tiles/6908")
    assert malformed.status_code == 404 and malformed.json()["kind"] == "UnknownTile"


def test_every_response_carries_a_request_id_and_echoes_the_client_s(client):
    minted = client.get("/api/v1/health")
    assert minted.headers["X-Request-Id"]
    echoed = client.get("/api/v1/health", headers={"X-Request-Id": "abc-123"})
    assert echoed.headers["X-Request-Id"] == "abc-123"


def test_an_unexpected_failure_is_a_plain_500_with_the_request_id(tmp_path, data_root, monkeypatch):
    settings = ServerSettings(data_root=data_root, static_dir=tmp_path / "static")
    services = _services(data_root)

    def explode(text):
        raise RuntimeError("the disk caught fire")

    monkeypatch.setattr(services.catalog, "tiles", explode)
    client = TestClient(build_app(settings, services), raise_server_exceptions=False)
    response = client.get("/api/v1/cities/ahmedabad/tiles", headers={"X-Request-Id": "r1"})
    assert response.status_code == 500
    assert response.json() == {"error": "internal error", "request_id": "r1"}


def test_the_pages_are_served_and_unknown_api_paths_are_404_json(client):
    assert client.get("/pages/index.html").status_code == 200
    assert client.get("/pages/model_pipeline.html").status_code == 200
    unknown = client.get("/api/v1/nothing-here")
    assert unknown.status_code == 404 and "no route" in unknown.json()["error"]


def test_without_a_built_client_every_page_route_says_how_to_build_it(client):
    response = client.get("/")
    assert response.status_code == 503 and "make frontend" in response.text
    assert client.get("/cities/ahmedabad").status_code == 503


def test_a_built_client_is_served_for_every_page_route_with_its_assets(tmp_path, data_root):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>client</title>")
    (static / "assets" / "index-abc123.js").write_text("console.log(1)")
    (static / "favicon.ico").write_bytes(b"icon")
    (tmp_path / "secret.txt").write_text("no")
    settings = ServerSettings(data_root=data_root, static_dir=static)
    client = TestClient(build_app(settings, _services(data_root)))
    for path in ("/", "/cities/ahmedabad", "/results"):
        page = client.get(path)
        assert page.status_code == 200 and "client" in page.text, path
        assert page.headers["Cache-Control"] == "no-store"
    assert client.get("/assets/index-abc123.js").text == "console.log(1)"
    assert client.get("/favicon.ico").content == b"icon"
    assert client.get("/../secret.txt").status_code in (200, 404)
    assert client.get("/../secret.txt").text != "no"
    assert client.get("/api/v1/nope").status_code == 404


def test_a_request_for_another_host_name_is_refused(client):
    assert client.get("/api/v1/health", headers={"Host": "evil.example"}).status_code == 400


def test_the_server_never_describes_tiles_on_a_request(tmp_path):
    settings = ServerSettings(data_root=tmp_path / "data", static_dir=tmp_path / "static")
    (tmp_path / "data" / "tiles").mkdir(parents=True)
    services = Services.open(settings)
    with pytest.raises(MissingStage, match="sdc tile list"):
        services.catalog.tiles("ahmedabad")


def test_the_openapi_schema_is_served(client):
    schema = client.get("/api/openapi.json").json()
    assert "/api/v1/cities/{city}/tiles/{tile}/report" in schema["paths"]
    assert client.get("/api/docs").status_code == 200
