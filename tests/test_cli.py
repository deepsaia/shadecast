"""Command line surface. No network, no engine and no database, so these stay fast."""

import json
import os

import pytest
from support import synthetic_tile
from typer.testing import CliRunner

from shadecast import cities
from shadecast.cities import City
from shadecast.cli import app
from shadecast.console import build_table, corpus_table, result_table
from shadecast.corpus import tile_paths
from shadecast.corpus.urban_centres import UrbanCentres
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.tile_index import TileIndex

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
    catalog = CityCatalog(dict(FIXTURE), _no_database, TileIndex(tmp_path, _no_tiles))
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


def test_results_with_nothing_generated_say_so():
    result = runner.invoke(app, ["results"])
    assert result.exit_code == 0, result.output
    assert "no tile with physics" in result.stdout


def test_runs_list_what_is_generating_now(tmp_path):
    surrogate = tmp_path / "6143" / "t43N_249_2547" / "surrogate"
    surrogate.mkdir(parents=True)
    (surrogate / ".generating.lock").write_text(str(os.getpid()))
    result = runner.invoke(app, ["runs", "--json"])
    assert result.exit_code == 0, result.output
    [run] = json.loads(result.stdout)
    assert run["kind"] == "generation" and run["alive"] is True
    table = runner.invoke(app, ["runs"])
    assert "generation" in table.stdout and "t43N_249_2547" in table.stdout


def test_runs_with_nothing_running_say_so():
    result = runner.invoke(app, ["runs"])
    assert result.exit_code == 0, result.output
    assert "nothing is running" in result.stdout
