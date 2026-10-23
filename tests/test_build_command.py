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


def test_build_a_named_tile_goes_into_the_tile_layout(tmp_path):
    result = runner.invoke(app, ["build", "ahmedabad", "--tile", "t43N_250_2546"])
    assert result.exit_code == 0, result.output
    assert [
        ("ahmedabad", "t43N_250_2546", str(tmp_path / "6143" / "t43N_250_2546" / "bundle"))
    ] == CALLS
    assert "t43N_250_2546" in result.stdout


def test_build_without_a_tile_takes_the_densest_and_says_so():
    result = runner.invoke(app, ["build", "ahmedabad"])
    assert result.exit_code == 0, result.output
    assert [call[1] for call in CALLS] == ["t43N_249_2547"]
    assert "densest" in result.stdout


def test_build_all_takes_the_densest_tile_of_every_selected_city():
    result = runner.invoke(app, ["build", "--all"])
    assert result.exit_code == 0, result.output
    assert [call[0] for call in CALLS] == ["ahmedabad", "london"]


def test_build_refuses_a_tile_with_all_or_a_malformed_tile():
    assert runner.invoke(app, ["build", "--all", "--tile", "t43N_250_2546"]).exit_code != 0
    assert runner.invoke(app, ["build", "ahmedabad", "--tile", "6908"]).exit_code != 0
    assert CALLS == []


def test_build_rejects_an_unknown_city():
    assert runner.invoke(app, ["build", "atlantis"]).exit_code != 0
    assert CALLS == []


def test_tile_ids_parse_before_anything_is_built():
    assert Tile.from_id("t43N_250_2546").id == "t43N_250_2546"
