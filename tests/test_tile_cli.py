"""The tile command group. No network: the database and the rasters are fixtures."""

import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from shadecast import tile_cli
from shadecast.cli import app
from shadecast.corpus import tile_paths
from shadecast.corpus.urban_centre import UrbanCentre
from shadecast.corpus.urban_centres import UrbanCentres

runner = CliRunner()

COLUMNS = (
    "ID_UC_G0",
    "GC_UCN_MAI_2025",
    "GC_UCN_LIS_2025",
    "GC_CNT_GAD_2025",
    "GC_UCA_KM2_2025",
    "GC_POP_TOT_2025",
    "GC_DEV_WIG_2025",
    "CL_KOP_CUR_2025",
    "lon",
    "lat",
)
ROWS = [(6143, "Ahmedabad", "Ahmedabad", "India", 6, 7898649.8, "Lower Middle", "6", 72.6, 23.0)]
TILES = [
    {
        "id": "t43N_249_2547",
        "x_km": 6897,
        "y_km": 2808,
        "population_2020": 9000.0,
        "density_2020_per_km2": 9000.0,
        "built_fraction": 0.9,
        "mean_height_m": 9.0,
    },
    {
        "id": "t43N_250_2547",
        "x_km": 6898,
        "y_km": 2808,
        "population_2020": 7000.0,
        "density_2020_per_km2": 7000.0,
        "built_fraction": 0.8,
        "mean_height_m": 8.0,
    },
    {
        "id": "t43N_249_2546",
        "x_km": 6897,
        "y_km": 2807,
        "population_2020": 5000.0,
        "density_2020_per_km2": 5000.0,
        "built_fraction": 0.5,
        "mean_height_m": 6.0,
    },
    {
        "id": "t43N_250_2546",
        "x_km": 6898,
        "y_km": 2807,
        "population_2020": 3000.0,
        "density_2020_per_km2": 3000.0,
        "built_fraction": 0.4,
        "mean_height_m": 5.0,
    },
    {
        "id": "t43N_251_2546",
        "x_km": 6899,
        "y_km": 2807,
        "population_2020": 1000.0,
        "density_2020_per_km2": 1000.0,
        "built_fraction": 0.1,
        "mean_height_m": 3.0,
    },
    {
        "id": "t43N_251_2547",
        "x_km": 6899,
        "y_km": 2808,
        "population_2020": 0.0,
        "density_2020_per_km2": 0.0,
        "built_fraction": 0.0,
        "mean_height_m": 0.0,
    },
]


def _fixture_centres() -> UrbanCentres:
    return UrbanCentres(pd.DataFrame(ROWS, columns=COLUMNS))


def _fixture_describe(centre: UrbanCentre) -> list[dict]:
    return [dict(row) for row in TILES]


def _refuse_describe(centre: UrbanCentre) -> list[dict]:
    raise AssertionError("tiles were described again although tiles.json exists")


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setattr(tile_cli, "load_centres", _fixture_centres)
    monkeypatch.setattr(tile_cli, "describe", _fixture_describe)
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)


def test_help_lists_the_tile_commands():
    result = runner.invoke(app, ["tile", "--help"])
    assert result.exit_code == 0
    for command in ("list", "select", "stats", "path", "status"):
        assert command in result.stdout


def test_list_writes_tiles_json_and_prints_the_densest_first(tmp_path):
    result = runner.invoke(app, ["tile", "list", "ahmedabad", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["count"] == 6
    assert payload["urban_centre"]["id"] == 6143
    assert [row["id"] for row in payload["tiles"]][:2] == ["t43N_249_2547", "t43N_250_2547"]
    written = json.loads((tmp_path / "6143" / "tiles.json").read_text())
    assert written["count"] == 6
    table = runner.invoke(app, ["tile", "list", "6143", "--limit", "2"])
    assert "t43N_249_2547" in table.stdout and "t43N_251_2546" not in table.stdout


def test_list_reads_the_written_file_instead_of_describing_again(monkeypatch):
    assert runner.invoke(app, ["tile", "list", "ahmedabad"]).exit_code == 0
    monkeypatch.setattr(tile_cli, "describe", _refuse_describe)
    assert runner.invoke(app, ["tile", "list", "ahmedabad"]).exit_code == 0
    assert runner.invoke(app, ["tile", "list", "ahmedabad", "--refresh"]).exit_code == 1


def _select(*args: str) -> list[dict]:
    result = runner.invoke(app, ["tile", "select", "ahmedabad", *args, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_select_densest_takes_the_top_k():
    assert [row["id"] for row in _select("--densest", "2")] == ["t43N_249_2547", "t43N_250_2547"]


def test_select_stratified_spreads_over_built_fraction_terciles():
    chosen = _select("--stratified", "3")
    assert [row["id"] for row in chosen] == ["t43N_249_2547", "t43N_249_2546", "t43N_251_2546"]


def test_select_ids_keeps_the_asked_order():
    chosen = _select("--ids", "t43N_250_2546", "--ids", "t43N_249_2547")
    assert [row["id"] for row in chosen] == ["t43N_250_2546", "t43N_249_2547"]


def test_select_random_is_reproducible_and_populated():
    first = _select("--random", "2", "--seed", "1")
    assert first == _select("--random", "2", "--seed", "1")
    assert all(row["population_2020"] > 0 for row in first)


def test_select_needs_exactly_one_strategy():
    assert runner.invoke(app, ["tile", "select", "ahmedabad"]).exit_code != 0
    both = runner.invoke(
        app, ["tile", "select", "ahmedabad", "--densest", "1", "--stratified", "1"]
    )
    assert both.exit_code != 0


def test_select_refuses_an_unknown_tile_id_by_name():
    result = runner.invoke(app, ["tile", "select", "ahmedabad", "--ids", "t1_1"])
    assert result.exit_code == 1
    assert "t1_1" in result.output


def test_tiles_path_is_keyed_by_urban_centre_id(tmp_path):
    centre = _fixture_centres().by_id(6143)
    assert tile_cli.tiles_path(centre) == Path(tmp_path) / "6143" / "tiles.json"


def test_stats_summarise_the_described_tiles():
    result = runner.invoke(app, ["tile", "stats", "ahmedabad", "--json"])
    assert result.exit_code == 0, result.output
    stats = json.loads(result.stdout)
    assert stats["tiles"] == 6
    assert stats["populated_tiles"] == 5
    assert stats["population_2020"] == 25000.0
    assert stats["urban_centre"]["population_2025"] == 7898650
    assert "built_fraction" in runner.invoke(app, ["tile", "stats", "ahmedabad"]).stdout


def test_path_prints_where_a_tile_lives_and_its_stages(tmp_path):
    result = runner.invoke(app, ["tile", "path", "ahmedabad", "t43N_249_2546", "--json"])
    assert result.exit_code == 0, result.output
    listed = json.loads(result.stdout)
    assert listed["tile"] == "t43N_249_2546"
    assert listed["bundle"] == str(tmp_path / "6143" / "t43N_249_2546" / "bundle")
    assert listed["stages"]["bundle"] is False


def test_path_refuses_a_malformed_tile_id():
    result = runner.invoke(app, ["tile", "path", "ahmedabad", "6908"])
    assert result.exit_code == 1


def _built(root: Path, tile_id: str, *, with_physics: bool) -> None:
    tile = root / "6143" / tile_id
    (tile / "bundle").mkdir(parents=True)
    (tile / "bundle" / "provenance.json").write_text("{}")
    if with_physics:
        (tile / "surrogate" / "baseline").mkdir(parents=True)
        (tile / "surrogate" / "baseline" / "tmrt_daylight.npy").write_bytes(b"")


def test_status_reports_k_of_n_per_stage(tmp_path):
    _built(tmp_path, "t43N_249_2547", with_physics=True)
    _built(tmp_path, "t43N_250_2547", with_physics=False)
    result = runner.invoke(app, ["tile", "status", "ahmedabad", "--json"])
    assert result.exit_code == 0, result.output
    status = json.loads(result.stdout)
    assert status["tiles"] == 6
    assert status["totals"] == {
        "bundle": 2,
        "baseline": 1,
        "surrogate": 0,
        "model": 0,
        "results": 0,
    }
    assert [row["tile"] for row in status["rows"]] == ["t43N_249_2547", "t43N_250_2547"]
    table = runner.invoke(app, ["tile", "status", "ahmedabad"])
    assert "2 of 6" in table.stdout


def test_status_of_an_untouched_centre_is_zero_of_n(tmp_path):
    status = json.loads(runner.invoke(app, ["tile", "status", "ahmedabad", "--json"]).stdout)
    assert status["totals"]["bundle"] == 0 and status["tiles"] == 6
