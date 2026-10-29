"""A scenario is answered over the API: outcomes as JSON, the fields as one NPY stack, wrong levers as 400."""

import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from support import synthetic_tile
from support.fake_surrogate import FakeSurrogate
from support.fixtures import fixture_centres
from support.fixtures import fixture_corpus
from support.fixtures import fixture_tiles

from shadecast.server.app import build_app
from shadecast.server.services import Services
from shadecast.server.settings import ServerSettings
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.findings_report import FindingsReport
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.results_report import ResultsReport
from shadecast.service.run_status import RunStatus
from shadecast.service.scenario_service import ScenarioService
from shadecast.service.selection import Selection
from shadecast.service.tile_index import TileIndex
from shadecast.service.tile_reporter import TileReporter

SCENARIO = f"/api/v1/cities/ahmedabad/tiles/{synthetic_tile.TILE_ID}/scenario"
SCATTERED_QUARTER = {"arrangement": "scattered", "coverage": 0.25}


def _services(data_root: Path) -> Services:
    models = ModelCatalog(data_root / "models")
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()),
        fixture_centres,
        TileIndex(data_root / "tiles", fixture_tiles),
        models,
    )
    return Services(
        catalog=catalog,
        reporter=TileReporter(catalog),
        results=ResultsReport(catalog, data_root),
        findings=FindingsReport(data_root),
        models=models,
        runs=RunStatus(catalog, data_root / "models"),
        scenarios=ScenarioService(catalog, models, FakeSurrogate.load),
    )


@pytest.fixture
def client(tmp_path) -> TestClient:
    root = tmp_path / "data"
    tile = synthetic_tile.write_bundle(root / "tiles")
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    synthetic_tile.write_model(root / "models")
    settings = ServerSettings(data_root=root, static_dir=tmp_path / "static")
    return TestClient(build_app(settings, _services(root)))


def _stack(client: TestClient, params: dict) -> np.ndarray:
    response = client.get(f"{SCENARIO}/field", params=params)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/x-npy"
    return np.load(io.BytesIO(response.content), allow_pickle=False)


def test_the_outcomes_answer_the_levers_as_json(client):
    response = client.get(SCENARIO, params=SCATTERED_QUARTER)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert (payload["trees"], payload["arrangement"], payload["model_id"]) == (
        48,
        "scattered",
        synthetic_tile.MODEL_ID,
    )
    assert payload["exposure_drop"] > 0 and payload["baseline_exposure"] == synthetic_tile.BASELINE_C


def test_a_unit_cost_reprices_the_scenario(client):
    listed = client.get(SCENARIO, params=SCATTERED_QUARTER).json()
    dearer = client.get(SCENARIO, params={**SCATTERED_QUARTER, "unit_cost": 80, "maintenance": 0.08}).json()
    assert dearer["cost_usd"] == pytest.approx(2 * listed["cost_usd"]) and dearer["unit_cost"] == 80.0
    assert dearer["exposure_drop"] == listed["exposure_drop"]
    assert client.get(SCENARIO, params={**SCATTERED_QUARTER, "maintenance": 1.5}).status_code == 400


def test_the_threshold_is_a_lever_too(client):
    payload = client.get(SCENARIO, params={**SCATTERED_QUARTER, "threshold": 49}).json()
    assert payload["threshold"] == 49.0 and payload["people"] > 0
    assert client.get(SCENARIO, params={**SCATTERED_QUARTER, "threshold": 5}).status_code == 400


def test_a_budget_sets_the_coverage_and_is_not_exceeded(client):
    payload = client.get(SCENARIO, params={"budget_usd": 10_000}).json()
    assert 0 < payload["cost_usd"] <= 10_000 and payload["coverage"] > 0


def test_the_fields_come_cooling_first_then_placement_and_shrink_on_request(client):
    cooling, placement = _stack(client, SCATTERED_QUARTER)
    assert cooling.dtype == np.float32 and cooling.shape == (synthetic_tile.SIZE, synthetic_tile.SIZE)
    assert np.array_equal(cooling > 0, placement > 0) and int(placement.sum()) == 48
    assert _stack(client, {**SCATTERED_QUARTER, "size": 8}).shape == (2, 8, 8)


def test_wrong_levers_are_400_with_the_reason(client):
    neither = client.get(SCENARIO)
    assert neither.status_code == 400 and "exactly one of coverage and budget_usd" in neither.json()["error"]
    both = client.get(SCENARIO, params={"coverage": 0.1, "budget_usd": 5})
    assert both.status_code == 400
    orchard = client.get(SCENARIO, params={"coverage": 0.1, "arrangement": "orchard"})
    assert orchard.status_code == 400 and orchard.json()["kind"] == "UnknownArrangement"
    shade = client.get(SCENARIO, params={"coverage": 0.1, "kind": "shade"})
    assert shade.status_code == 400 and "no surrogate yet" in shade.json()["error"]


def test_an_unknown_city_stays_404(client):
    response = client.get(f"/api/v1/cities/atlantis/tiles/{synthetic_tile.TILE_ID}/scenario", params={"coverage": 0.1})
    assert response.status_code == 404 and response.json()["kind"] == "UnknownCity"
