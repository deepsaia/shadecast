"""Command line surface. No network, no engine and no database, so these stay fast."""

import json
import os
from pathlib import Path

import pytest
from support import synthetic_tile
from typer.testing import CliRunner

from shadecast import cities, tile_cli
from shadecast.cities import City
from shadecast.cli import app
from shadecast.console import build_table, corpus_table, result_table
from shadecast.corpus import tile_paths
from shadecast.corpus.urban_centres import UrbanCentres
from shadecast.service import experiment_service, plan_service
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.selection import Selection
from shadecast.service.tile_index import TileIndex
from shadecast.sim.result import RunResult
from shadecast.surrogate import dataset

runner = CliRunner()

FIXTURE = {
    "ahmedabad": City(
        "ahmedabad",
        6143,
        "Ahmedabad",
        "India",
        23.02,
        72.6,
        "BSh",
        "LM",
        "South Asia",
        7898650,
        365,
    ),
    "london": City(
        "london",
        5816,
        "London",
        "United Kingdom",
        51.5,
        -0.1,
        "Cfb",
        "H",
        "Europe",
        10408332,
        1649,
        True,
    ),
}


def _fixture_corpus(entries=None, centres=None) -> dict[str, City]:
    return dict(FIXTURE)


def _no_database() -> UrbanCentres:
    raise AssertionError("the database is not needed to list the selection")


def _no_tiles(centre: object) -> list[dict]:
    raise AssertionError("tiles are not described to list the selection")


@pytest.fixture(autouse=True)
def _offline_corpus(monkeypatch, tmp_path):
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setattr(cities, "corpus", _fixture_corpus)
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    monkeypatch.setattr(tile_paths, "MODELS_ROOT", tmp_path / "models")


def test_help_lists_every_command():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("cities", "build", "plan", "run"):
        assert command in result.stdout


def test_cities_renders_the_selection_and_its_stratification():
    result = runner.invoke(app, ["cities"])
    assert result.exit_code == 0, result.output
    assert "ahmedabad" in result.stdout
    assert "Global South" in result.stdout


def test_cities_json_carries_the_summary_and_what_each_city_has(tmp_path):
    bundle = tmp_path / "6143" / "t43N_249_2547" / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "provenance.json").write_text("{}")
    result = runner.invoke(app, ["cities", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert "summary" in payload
    ahmedabad = payload["cities"][0]
    assert ahmedabad["key"] == "ahmedabad"
    assert ahmedabad["stages"] == {
        "tiles": 365,
        "bundle": 1,
        "baseline": 0,
        "physics": 0,
        "model": 0,
        "results": 0,
    }


def test_build_without_a_city_is_rejected():
    result = runner.invoke(app, ["build"])
    assert result.exit_code != 0


def test_build_rejects_an_unknown_city():
    result = runner.invoke(app, ["build", "atlantis"])
    assert result.exit_code != 0


def test_corpus_table_has_a_row_per_city(tmp_path):
    catalog = CityCatalog(
        Selection.resolved(dict(FIXTURE)),
        _no_database,
        TileIndex(tmp_path, _no_tiles),
        ModelCatalog(tmp_path / "models"),
    )
    table = corpus_table(catalog.cities())
    assert table.row_count == len(FIXTURE)


def test_build_table_starts_empty():
    assert build_table().row_count == 0


def test_result_table_renders_a_scored_plan():
    payload = {
        "city": "testville",
        "intervention": "tree",
        "design_day": "2024-05-23",
        "baseline": {"exposure": 55.0, "people_at_risk": 40000.0, "cost_usd": 0.0},
        "plan": {"exposure": 49.0, "people_at_risk": 32000.0, "cost_usd": 1000.0},
        "benefit": {
            "delta_exposure_C": 6.0,
            "delta_people_at_risk": 8000.0,
            "excess_reduced_per_1k_usd": 31.7,
        },
        "tmrt_drop_where_planted_C": 17.8,
        "spillover_C": 1.5,
    }
    assert result_table(payload).row_count > 0


def test_results_report_every_tile_with_physics(tmp_path):
    tile = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    result = runner.invoke(app, ["results", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["totals"] == {"cities": 1, "plans": 3, "budget_min_m": 0.0, "budget_max_m": 0.0}
    table = runner.invoke(app, ["results"])
    assert table.exit_code == 0, table.output
    assert "Ahmedabad" in table.stdout


def test_results_with_nothing_simulated_say_so():
    result = runner.invoke(app, ["results"])
    assert result.exit_code == 0, result.output
    assert "no tile with physics" in result.stdout


def test_runs_list_what_is_simulating_now(tmp_path):
    physics = tmp_path / "6143" / "t43N_249_2547" / "physics"
    physics.mkdir(parents=True)
    (physics / ".simulating.lock").write_text(str(os.getpid()))
    result = runner.invoke(app, ["runs", "--json"])
    assert result.exit_code == 0, result.output
    [run] = json.loads(result.stdout)
    assert run["kind"] == "simulation" and run["alive"] is True
    table = runner.invoke(app, ["runs"])
    assert "simulation" in table.stdout and "t43N_249_2547" in table.stdout


def test_runs_with_nothing_running_say_so():
    result = runner.invoke(app, ["runs"])
    assert result.exit_code == 0, result.output
    assert "nothing is running" in result.stdout


def test_simulate_baseline_produces_the_physics_for_a_tile(tmp_path, monkeypatch):
    def fake_run(base_path, date, **kwargs):
        tmrt = Path(base_path) / "output_folder" / "0_0" / "TMRT_0_0.tif"
        synthetic_tile.write_hourly_raster(tmrt)
        return RunResult(base_path=Path(base_path), seconds=9.0, tmrt_path=tmrt, returncode=0)

    monkeypatch.setattr(dataset, "run", fake_run)
    monkeypatch.setattr(tile_cli, "load_centres", _no_database)
    tile = synthetic_tile.write_bundle(tmp_path)
    result = runner.invoke(app, ["simulate", "baseline", "ahmedabad", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["kept"] is False
    assert (tile / "physics" / "baseline" / "tmrt_daylight.npy").exists()
    again = runner.invoke(app, ["simulate", "baseline", "ahmedabad"])
    assert again.exit_code == 0 and "kept" in again.stdout


def test_plan_reports_a_scored_plan_for_a_tile(tmp_path, monkeypatch):
    def fake_evaluate(bundle, kind="tree", budget_usd=10_000_000.0, work_root=None):
        return {
            "city": "bundle",
            "tier": "A",
            "design_day": synthetic_tile.DESIGN_DAY,
            "intervention": kind,
            "pixels": 10,
            "baseline": {"exposure": 50.0, "people_at_risk": 512.0, "cost_usd": 0.0},
            "plan": {"exposure": 49.0, "people_at_risk": 500.0, "cost_usd": budget_usd},
            "benefit": {
                "delta_exposure_C": 1.0,
                "delta_people_at_risk": 12.0,
                "excess_reduced_per_1k_usd": 2.0,
                "cost_usd": budget_usd,
            },
            "tmrt_drop_where_planted_C": 2.0,
            "tmrt_drop_all_outdoor_C": 0.5,
            "spillover_C": 0.1,
            "engine_seconds": {"baseline": 1.0, "plan": 2.0},
        }

    monkeypatch.setattr(plan_service, "evaluate", fake_evaluate)
    synthetic_tile.write_bundle(tmp_path)
    result = runner.invoke(app, ["plan", "ahmedabad", "--budget", "5000000", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["exposure_drop"] == 1.0 and payload["cost_usd"] == 5_000_000.0
    table = runner.invoke(app, ["plan", "ahmedabad"])
    assert table.exit_code == 0, table.output
    assert "outdoor Tmrt" in table.stdout


def test_experiments_run_over_a_city_by_name(tmp_path, monkeypatch):
    def fake_factorial(cities, out_path):
        Path(out_path).write_text("[]")
        return [{"city": cities[0][0], "kind": "tree"}]

    monkeypatch.setattr(experiment_service, "run_factorial", fake_factorial)
    tile = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(tile)
    result = runner.invoke(
        app, ["experiments", "factorial", "ahmedabad", "--out", str(tmp_path / "f.json"), "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["rows"] == 1
    missing = runner.invoke(app, ["experiments", "targeting", "london"])
    assert missing.exit_code == 1 and "sdc build london" in missing.output
