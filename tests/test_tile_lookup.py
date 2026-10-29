"""A city is addressed by its name; the lookup finds its built tiles without rebuilding anything."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from shadecast import simulate_cli
from shadecast.cli import app
from shadecast.corpus import tile_lookup
from shadecast.corpus import tile_paths
from shadecast.service import simulation_service

runner = CliRunner()


def _bundle(root: Path, centre: int, tile: str) -> Path:
    bundle = root / str(centre) / tile / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "provenance.json").write_text(
        json.dumps({"city": {"key": "ahmedabad"}, "tile": {"id": tile, "urban_centre": centre}})
    )
    return bundle


def test_a_corpus_key_and_a_bare_id_resolve_without_the_database():
    assert tile_lookup.centre_id("ahmedabad") == 6143
    assert tile_lookup.centre_id("6143") == 6143


def test_only_tiles_with_a_bundle_count_as_built(tmp_path):
    _bundle(tmp_path, 6143, "t43N_249_2547")
    (tmp_path / "6143" / "t43N_250_2547").mkdir()  # a directory without a bundle
    found = tile_lookup.built_tiles("ahmedabad", tmp_path)
    assert [paths.tile.id for paths in found] == ["t43N_249_2547"]


def test_one_built_tile_is_chosen_named_or_refused(tmp_path):
    with pytest.raises(ValueError, match="run 'sdc build ahmedabad' first"):
        tile_lookup.one_built_tile("ahmedabad", None, tmp_path)
    _bundle(tmp_path, 6143, "t43N_249_2547")
    assert tile_lookup.one_built_tile("ahmedabad", None, tmp_path).tile.id == "t43N_249_2547"
    _bundle(tmp_path, 6143, "t43N_250_2547")
    with pytest.raises(ValueError, match="add --tile"):
        tile_lookup.one_built_tile("ahmedabad", None, tmp_path)
    assert tile_lookup.one_built_tile("ahmedabad", "t43N_250_2547", tmp_path).tile.id == "t43N_250_2547"
    with pytest.raises(ValueError, match="no built tile t43N_251_2547"):
        tile_lookup.one_built_tile("ahmedabad", "t43N_251_2547", tmp_path)


def test_simulate_takes_a_city_name_and_writes_beside_its_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    monkeypatch.setattr(tile_paths, "MODELS_ROOT", tmp_path / "models")
    bundle = _bundle(tmp_path, 6143, "t43N_249_2547")
    seen: dict = {}

    def fake_simulate(bundle_dir, destination, settings, progress):
        seen.update(bundle=Path(bundle_dir), destination=Path(destination), jobs=settings.jobs)
        progress.started("ahmedabad t43N_249_2547", total=1, done=1)
        return {"entries": 1, "manifest": []}

    monkeypatch.setattr(simulation_service, "simulate", fake_simulate)
    result = runner.invoke(app, ["simulate", "treeshade", "ahmedabad", "--jobs", "3"])
    assert result.exit_code == 0, result.output
    assert seen["bundle"] == bundle
    assert seen["destination"] == bundle.parent / "physics"
    assert seen["jobs"] == 3


def test_simulate_runs_each_listed_tile_or_all_of_them(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    monkeypatch.setattr(tile_paths, "MODELS_ROOT", tmp_path / "models")
    first = _bundle(tmp_path, 6143, "t43N_249_2547")
    second = _bundle(tmp_path, 6143, "t43N_250_2547")
    seen: list[Path] = []

    def fake_simulate(bundle_dir, destination, settings, progress):
        seen.append(Path(bundle_dir))
        progress.started("x", total=1, done=1)
        return {"entries": 1, "manifest": []}

    monkeypatch.setattr(simulation_service, "simulate", fake_simulate)
    result = runner.invoke(app, ["simulate", "treeshade", "ahmedabad", "--tiles", "t43N_250_2547"])
    assert result.exit_code == 0, result.output
    assert seen == [second]
    seen.clear()
    result = runner.invoke(app, ["simulate", "treeshade", "ahmedabad", "--tiles", "all"])
    assert result.exit_code == 0, result.output
    assert seen == [first, second]
    assert "tile 1 of 2" in result.stdout and "tile 2 of 2" in result.stdout


def test_simulate_without_tiles_takes_the_densest_built_one(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    monkeypatch.setattr(tile_paths, "MODELS_ROOT", tmp_path / "models")
    _bundle(tmp_path, 6143, "t43N_249_2547")
    dense = _bundle(tmp_path, 6143, "t43N_250_2547")
    with pytest.raises(ValueError, match=r"no tiles\.json"):
        tile_lookup.densest_built_tile("ahmedabad", tmp_path)
    (tmp_path / "6143" / "tiles.json").write_text(
        json.dumps(
            {
                "tiles": [
                    {"id": "t43N_249_2547", "population_2020": 100},
                    {"id": "t43N_250_2547", "population_2020": 900},
                ]
            }
        )
    )
    assert tile_lookup.densest_built_tile("ahmedabad", tmp_path).bundle == dense


def test_simulate_refuses_a_city_without_a_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    monkeypatch.setattr(tile_paths, "MODELS_ROOT", tmp_path / "models")
    result = runner.invoke(app, ["simulate", "treeshade", "ahmedabad"])
    assert result.exit_code == 1
    assert "sdc build ahmedabad" in result.output


def _physics(bundle: Path) -> Path:
    physics = bundle.parent / "physics"
    physics.mkdir()
    (physics / "manifest.json").write_text("{}")
    return physics


def test_resume_command_repeats_the_options():
    assert simulate_cli.resume_command("savannah", None, None, 4) == ("sdc simulate treeshade savannah --jobs 4")
    assert simulate_cli.resume_command("x/bundle", "t1", Path("o"), 1) == (
        "sdc simulate treeshade x/bundle --tiles t1 --out o"
    )
