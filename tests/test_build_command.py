"""The build command builds tiles into the tile layout. No network: the build itself is a double."""

import pytest
from support.fixtures import fixture_centres, fixture_corpus, fixture_provenance, fixture_tiles
from typer.testing import CliRunner

from shadecast import cli, tile_cli
from shadecast.cli import app
from shadecast.corpus import tile_paths
from shadecast.corpus.tile import Tile

runner = CliRunner()
CALLS: list[tuple[str, str, str]] = []


def _fake_build_tile(city, tile, paths):
    CALLS.append((city.key, tile.id, str(paths.bundle)))
    return fixture_provenance(city.key, tile.id)


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setenv("COLUMNS", "200")
    CALLS.clear()
    monkeypatch.setattr(cli.cities, "corpus", fixture_corpus)
    monkeypatch.setattr(cli, "build_tile", _fake_build_tile)
    monkeypatch.setattr(tile_cli, "load_centres", fixture_centres)
    monkeypatch.setattr(tile_cli, "describe", fixture_tiles)
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    monkeypatch.setattr(tile_paths, "MODELS_ROOT", tmp_path / "models")


def test_build_a_named_tile_goes_into_the_tile_layout(tmp_path):
    result = runner.invoke(app, ["build", "ahmedabad", "--tiles", "t43N_250_2546"])
    assert result.exit_code == 0, result.output
    assert [
        ("ahmedabad", "t43N_250_2546", str(tmp_path / "6143" / "t43N_250_2546" / "bundle"))
    ] == CALLS
    assert "t43N_250_2546" in result.stdout


def test_build_without_a_tile_takes_the_densest_and_says_so():
    result = runner.invoke(app, ["build", "ahmedabad"])
    assert result.exit_code == 0, result.output
    assert [call[1] for call in CALLS] == ["t43N_249_2547"]
    assert "bundle at" in result.stdout and "6143/t43N_249_2547/bundle" in result.stdout
    assert "next: sdc simulate treeshade ahmedabad --jobs 4" in result.stdout
    assert "1 of 6 tiles chosen" in result.stdout


def test_build_a_list_of_tiles_all_tiles_or_the_k_densest():
    result = runner.invoke(app, ["build", "ahmedabad", "--tiles", "t43N_249_2547,t43N_250_2546"])
    assert result.exit_code == 0, result.output
    assert [call[1] for call in CALLS] == ["t43N_249_2547", "t43N_250_2546"]
    assert "--tiles t43N_250_2546 --jobs 4" in result.stdout
    CALLS.clear()
    assert runner.invoke(app, ["build", "ahmedabad", "--tiles", "all"]).exit_code == 0
    assert len(CALLS) == 6
    CALLS.clear()
    assert runner.invoke(app, ["build", "ahmedabad", "--tiles="]).exit_code == 0
    assert len(CALLS) == 6
    CALLS.clear()
    assert runner.invoke(app, ["build", "ahmedabad", "--densest", "2"]).exit_code == 0
    assert [call[1] for call in CALLS] == ["t43N_249_2547", "t43N_250_2547"]
    CALLS.clear()
    assert runner.invoke(app, ["build", "ahmedabad", "--stratified", "3"]).exit_code == 0
    assert len(CALLS) == 3


def test_build_all_takes_the_densest_tile_of_every_selected_city():
    result = runner.invoke(app, ["build", "--all"])
    assert result.exit_code == 0, result.output
    assert [call[0] for call in CALLS] == ["ahmedabad", "london"]


def test_build_refuses_a_tile_with_all_or_a_malformed_tile():
    assert runner.invoke(app, ["build", "--all", "--tiles", "t43N_250_2546"]).exit_code != 0
    assert runner.invoke(app, ["build", "ahmedabad", "--tiles", "6908"]).exit_code != 0
    assert CALLS == []


def test_build_rejects_an_unknown_city():
    assert runner.invoke(app, ["build", "atlantis"]).exit_code != 0
    assert CALLS == []


def test_tile_ids_parse_before_anything_is_built():
    assert Tile.from_id("t43N_250_2546").id == "t43N_250_2546"
