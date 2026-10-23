"""Generated physics lands beside the bundle it came from when the bundle sits in a tile."""

from pathlib import Path

from shadecast import surrogate_cli
from shadecast.corpus import tile_paths


def test_a_tile_bundle_defaults_to_the_tile_surrogate_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path / "tiles")
    bundle = tmp_path / "tiles" / "6143" / "t43N_249_2547" / "bundle"
    bundle.mkdir(parents=True)
    assert surrogate_cli.default_out(bundle) == bundle.parent / "surrogate"


def test_a_bundle_outside_the_tile_layout_keeps_the_old_default(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path / "tiles")
    bundle = tmp_path / "corpus" / "savannah"
    bundle.mkdir(parents=True)
    assert surrogate_cli.default_out(bundle) == Path("data/surrogate") / "savannah"
