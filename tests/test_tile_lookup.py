"""A city is addressed by its name; the lookup finds its built tiles without rebuilding anything."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from shadecast import surrogate_cli
from shadecast.cli import app
from shadecast.corpus import tile_lookup, tile_paths
from shadecast.corpus.tile_selection import TileSelection

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
    assert (
        tile_lookup.one_built_tile("ahmedabad", "t43N_250_2547", tmp_path).tile.id
        == "t43N_250_2547"
    )
    with pytest.raises(ValueError, match="no built tile t43N_251_2547"):
        tile_lookup.one_built_tile("ahmedabad", "t43N_251_2547", tmp_path)


def test_generate_takes_a_city_name_and_writes_beside_its_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    bundle = _bundle(tmp_path, 6143, "t43N_249_2547")
    seen: dict = {}

    def fake_generate(bundle_dir, destination, settings, progress):
        seen.update(bundle=Path(bundle_dir), destination=Path(destination), jobs=settings.jobs)
        progress.start("ahmedabad t43N_249_2547", total=1, done=1)
        return {"entries": 1, "manifest": []}

    monkeypatch.setattr(surrogate_cli, "generate", fake_generate)
    result = runner.invoke(app, ["surrogate", "treeshade", "generate", "ahmedabad", "--jobs", "3"])
    assert result.exit_code == 0, result.output
    assert seen["bundle"] == bundle
    assert seen["destination"] == bundle.parent / "surrogate"
    assert seen["jobs"] == 3


def test_generate_runs_each_listed_tile_or_all_of_them(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    first = _bundle(tmp_path, 6143, "t43N_249_2547")
    second = _bundle(tmp_path, 6143, "t43N_250_2547")
    seen: list[Path] = []

    def fake_generate(bundle_dir, destination, settings, progress):
        seen.append(Path(bundle_dir))
        progress.start("x", total=1, done=1)
        return {"entries": 1, "manifest": []}

    monkeypatch.setattr(surrogate_cli, "generate", fake_generate)
    result = runner.invoke(
        app, ["surrogate", "treeshade", "generate", "ahmedabad", "--tiles", "t43N_250_2547"]
    )
    assert result.exit_code == 0, result.output
    assert seen == [second]
    seen.clear()
    result = runner.invoke(
        app, ["surrogate", "treeshade", "generate", "ahmedabad", "--tiles", "all"]
    )
    assert result.exit_code == 0, result.output
    assert seen == [first, second]
    assert "tile 1 of 2" in result.stdout and "tile 2 of 2" in result.stdout


def test_generate_without_tiles_takes_the_densest_built_one(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
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


def test_generate_refuses_a_city_without_a_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    result = runner.invoke(app, ["surrogate", "treeshade", "generate", "ahmedabad"])
    assert result.exit_code == 1
    assert "sdc build ahmedabad" in result.output


def _physics(bundle: Path) -> Path:
    surrogate = bundle.parent / "surrogate"
    surrogate.mkdir()
    (surrogate / "manifest.json").write_text("{}")
    return surrogate


def test_training_pairs_accept_keys_paths_and_mixed_pairs(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    bundle = _bundle(tmp_path, 6143, "t43N_249_2547")
    with pytest.raises(ValueError, match="no generated physics"):
        surrogate_cli.training_pairs("ahmedabad", None, None)
    _physics(bundle)
    assert surrogate_cli.training_pairs("ahmedabad", None, None) == [
        (bundle.parent / "surrogate", bundle)
    ]
    assert surrogate_cli.training_pairs("a/surrogate", Path("a/bundle"), None) == [
        (Path("a/surrogate"), Path("a/bundle"))
    ]
    mixed = surrogate_cli.training_pairs(None, None, ["ahmedabad", "x/s=x/b"])
    assert mixed == [(bundle.parent / "surrogate", bundle), (Path("x/s"), Path("x/b"))]
    second = _bundle(tmp_path, 6143, "t43N_250_2547")
    only_first = surrogate_cli.training_pairs("ahmedabad", None, None)
    assert only_first == [(bundle.parent / "surrogate", bundle)]  # the second has no physics yet
    with pytest.raises(ValueError, match="has no generated physics"):
        surrogate_cli.training_pairs("ahmedabad", None, None, "t43N_250_2547")
    _physics(second)
    both = surrogate_cli.training_pairs("ahmedabad", None, None)  # every tile with physics
    assert both == [(bundle.parent / "surrogate", bundle), (second.parent / "surrogate", second)]
    assert surrogate_cli.training_pairs("ahmedabad", None, None, "t43N_249_2547") == [
        (bundle.parent / "surrogate", bundle)
    ]
    with pytest.raises(ValueError, match="give a city key"):
        surrogate_cli.training_pairs(None, None, None)


def test_newest_model_is_picked_for_a_city(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    monkeypatch.setattr(surrogate_cli, "MODELS_ROOT", tmp_path / "models")
    bundle = _bundle(tmp_path, 6143, "t43N_249_2547")
    _physics(bundle)
    models = bundle.parent / "models"
    for name in (
        "response-unet-ahmedabad-20260826T143800",
        "response-unet-ahmedabad-20261023T121739",
    ):
        (models / name).mkdir(parents=True)
        (models / name / "model.pt").write_bytes(b"w")
    model_dir, surrogate_dir, found_bundle = surrogate_cli.newest_model("ahmedabad", None)
    assert model_dir.name == "response-unet-ahmedabad-20261023T121739"
    assert surrogate_dir == bundle.parent / "surrogate" and found_bundle == bundle
    named, _, _ = surrogate_cli.newest_model("ahmedabad", "response-unet-ahmedabad-20260826T143800")
    assert named.name == "response-unet-ahmedabad-20260826T143800"
    pooled = tmp_path / "models" / "response-unet-ahmedabad-2tiles-20261024T090000"
    pooled.mkdir(parents=True)
    (pooled / "model.pt").write_bytes(b"w")
    (pooled / "manifest.json").write_text(
        json.dumps(
            {
                "created": "2026-10-24T09:00:00+00:00",
                "data": {"tiles": [{"urban_centre": 6143}, {"urban_centre": 6143}]},
            }
        )
    )
    newest, _, _ = surrogate_cli.newest_model("ahmedabad", None)
    assert newest == pooled
    assert (
        surrogate_cli.assessment_name(pooled, bundle) == "assessment-ahmedabad-t43N_249_2547.json"
    )
    assert (
        surrogate_cli.assessment_name(models / "response-unet-ahmedabad-20260826T143800", bundle)
        == "assessment.json"
    )


def test_resume_command_repeats_the_options():
    assert surrogate_cli.resume_command("savannah", None, None, 4) == (
        "sdc surrogate treeshade generate savannah --jobs 4"
    )
    assert surrogate_cli.resume_command("x/bundle", "t1", Path("o"), 1) == (
        "sdc surrogate treeshade generate x/bundle --tiles t1 --out o"
    )


def test_training_can_pick_the_densest_or_stratified_tiles_with_physics(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    tiles = {"t43N_249_2547": (100, 0.1), "t43N_250_2547": (900, 0.6), "t43N_251_2547": (500, 0.3)}
    bundles = {tile: _physics(_bundle(tmp_path, 6143, tile)).parent / "bundle" for tile in tiles}
    _bundle(tmp_path, 6143, "t43N_252_2547")  # built, no physics: never chosen
    rows = [
        {"id": tile, "population_2020": pop, "density_2020_per_km2": pop, "built_fraction": built}
        for tile, (pop, built) in tiles.items()
    ] + [
        {
            "id": "t43N_252_2547",
            "population_2020": 5000,
            "density_2020_per_km2": 5000,
            "built_fraction": 0.9,
        }
    ]
    (tmp_path / "6143" / "tiles.json").write_text(json.dumps({"tiles": rows}))
    densest = surrogate_cli.training_pairs("ahmedabad", None, None, None, TileSelection(densest=2))
    assert [b.parent.name for _, b in densest] == ["t43N_250_2547", "t43N_251_2547"]
    spread = surrogate_cli.training_pairs(
        "ahmedabad", None, None, None, TileSelection(stratified=3)
    )
    assert sorted(b.parent.name for _, b in spread) == sorted(bundles)
    with pytest.raises(ValueError, match="not both"):
        TileSelection(densest=1, stratified=1)
