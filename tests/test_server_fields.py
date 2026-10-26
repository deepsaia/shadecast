"""Fields travel as NPY arrays, at native or requested size, and the remaining questions as JSON."""

import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from support import synthetic_tile
from support.fixtures import fixture_centres, fixture_corpus, fixture_tiles

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

TILE = synthetic_tile.TILE_ID


def _services(data_root: Path) -> Services:
    tiles_root = data_root / "tiles"
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()), fixture_centres, TileIndex(tiles_root, fixture_tiles)
    )
    return Services(
        catalog=catalog,
        reporter=TileReporter(catalog),
        results=ResultsReport(catalog, data_root),
        findings=FindingsReport(data_root),
        models=ModelCatalog(tiles_root, data_root / "models"),
        runs=RunStatus(catalog, data_root / "models"),
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


def _array(client: TestClient, path: str) -> np.ndarray:
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/x-npy"
    return np.load(io.BytesIO(response.content), allow_pickle=False)


def test_the_hourly_field_is_hours_first_and_shrinks_to_the_requested_size(client):
    hours = _array(client, f"/api/v1/cities/ahmedabad/tiles/{TILE}/fields/hours")
    assert hours.shape == (24, 16, 16) and hours.dtype == np.float32
    assert float(hours[5].max()) == 35.0
    small = _array(client, f"/api/v1/cities/ahmedabad/tiles/{TILE}/fields/hours?size=8")
    assert small.shape == (24, 8, 8) and small.dtype == np.float32
    assert float(small[5].max()) == 35.0


def test_context_cooling_and_placement_read_back(client):
    heights = _array(client, f"/api/v1/cities/ahmedabad/tiles/{TILE}/fields/context")
    assert (
        heights.shape == (16, 16) and float(heights[0, 0]) == 10.0 and float(heights[15, 15]) == 0.0
    )
    cooling = _array(client, f"/api/v1/cities/ahmedabad/tiles/{TILE}/fields/cooling")
    assert cooling.shape == (3, 16, 16)
    one = _array(
        client, f"/api/v1/cities/ahmedabad/tiles/{TILE}/fields/cooling?design=clustered_0101"
    )
    assert one.shape == (16, 16) and float(one[10, 10]) == 1.0 and float(one[0, 0]) == 0.0
    placement = _array(
        client, f"/api/v1/cities/ahmedabad/tiles/{TILE}/fields/placement?design=clustered_0101"
    )
    assert placement.dtype == np.bool_ and int(placement.sum()) == 16
    fraction = _array(
        client,
        f"/api/v1/cities/ahmedabad/tiles/{TILE}/fields/placement?design=clustered_0101&size=8",
    )
    assert fraction.dtype == np.float32 and 0.0 <= float(fraction.max()) <= 1.0
    assert float(fraction.sum()) > 0


def test_an_unknown_field_is_refused_and_a_missing_stage_is_named(client, tmp_path):
    assert (
        client.get(f"/api/v1/cities/ahmedabad/tiles/{TILE}/fields/temperature").status_code == 422
    )
    bare = synthetic_tile.write_bundle(tmp_path / "other" / "tiles")
    settings = ServerSettings(data_root=tmp_path / "other", static_dir=tmp_path / "static")
    client = TestClient(build_app(settings, _services(tmp_path / "other")))
    response = client.get(f"/api/v1/cities/ahmedabad/tiles/{bare.name}/fields/hours")
    assert response.status_code == 404 and response.json()["stage"] == "baseline"


def test_channels_and_models(client, data_root):
    channels = client.get("/api/v1/channels").json()
    assert [channel["key"] for channel in channels] == ["treeshade"]
    assert client.get("/api/v1/channels/treeshade/models?city=ahmedabad").json() == []
    model = (
        data_root / "tiles" / "6143" / TILE / "models" / "response-unet-ahmedabad-20261023T121739"
    )
    model.mkdir(parents=True)
    (model / "model.pt").write_bytes(b"w")
    listed = client.get("/api/v1/channels/treeshade/models?city=ahmedabad").json()
    assert [entry["id"] for entry in listed] == [model.name] and listed[0]["tile"] == TILE
    named = client.get(f"/api/v1/channels/treeshade/models/{model.name}?city=ahmedabad").json()
    assert named["id"] == model.name
    assert client.get("/api/v1/channels/albedo/models?city=ahmedabad").status_code == 404
    everyone = client.get("/api/v1/channels/treeshade/models").json()
    assert [entry["id"] for entry in everyone] == [model.name]
    assert everyone[0].get("urban_centres") == [6143]
    assert client.get("/api/v1/channels/treeshade/models/nope?city=ahmedabad").status_code == 404


def test_results_findings_references_and_runs(client, data_root):
    results = client.get("/api/v1/results").json()
    assert results["totals"]["plans"] == 3 and results["cities"][0]["key"] == "ahmedabad"
    findings = client.get("/api/v1/findings").json()
    assert set(findings) == {"surrogate", "factorial", "targeting", "channel"}
    references = client.get("/api/v1/references").json()
    assert references and "sources" in references[0]
    assert client.get("/api/v1/runs").json() == []
    (data_root / "tiles" / "6143" / TILE / "surrogate" / ".generating.lock").write_text("")
    [run] = client.get("/api/v1/runs").json()
    assert run["kind"] == "generation" and run["alive"] is False
