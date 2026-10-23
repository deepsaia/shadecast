"""A city is addressed by its name; the lookup finds its built tiles without rebuilding anything."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from shadecast import surrogate_cli
from shadecast.cli import app
from shadecast.corpus import tile_lookup, tile_paths

runner = CliRunner()


def _bundle(root: Path, centre: int, tile: str) -> Path:
    bundle = root / str(centre) / tile / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "provenance.json").write_text(json.dumps({"city": {"key": "ahmedabad"}}))
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
    result = runner.invoke(app, ["surrogate", "generate", "ahmedabad", "--jobs", "3"])
    assert result.exit_code == 0, result.output
    assert seen["bundle"] == bundle
    assert seen["destination"] == bundle.parent / "surrogate"
    assert seen["jobs"] == 3


def test_generate_refuses_a_city_without_a_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    result = runner.invoke(app, ["surrogate", "generate", "ahmedabad"])
    assert result.exit_code == 1
    assert "sdc build ahmedabad" in result.output


def test_training_pairs_accept_keys_paths_and_mixed_pairs(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    bundle = _bundle(tmp_path, 6143, "t43N_249_2547")
    assert surrogate_cli.training_pairs("ahmedabad", None, None) == [
        (bundle.parent / "surrogate", bundle)
    ]
    assert surrogate_cli.training_pairs("a/surrogate", Path("a/bundle"), None) == [
        (Path("a/surrogate"), Path("a/bundle"))
    ]
    mixed = surrogate_cli.training_pairs(None, None, ["ahmedabad", "x/s=x/b"])
    assert mixed == [(bundle.parent / "surrogate", bundle), (Path("x/s"), Path("x/b"))]
    with pytest.raises(ValueError, match="give a city key"):
        surrogate_cli.training_pairs(None, None, None)


def test_newest_model_is_picked_for_a_city(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    bundle = _bundle(tmp_path, 6143, "t43N_249_2547")
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


def test_resume_command_repeats_the_options():
    assert surrogate_cli.resume_command("savannah", None, None, "tree", 4) == (
        "sdc surrogate generate savannah --jobs 4"
    )
    assert surrogate_cli.resume_command("x/bundle", "t1", Path("o"), "shade", 1) == (
        "sdc surrogate generate x/bundle --tile t1 --out o --kind shade"
    )
