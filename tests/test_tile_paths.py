"""One layout for everything a tile produces, keyed by urban centre id and tile id."""

from pathlib import Path

from shadecast.corpus.tile import Tile
from shadecast.corpus.tile_paths import TilePaths


def test_paths_are_keyed_by_urban_centre_and_tile(tmp_path):
    paths = TilePaths(tmp_path, 6143, Tile(6908, 2816))
    assert paths.root == tmp_path / "6143" / "t6908_2816"
    assert paths.bundle == tmp_path / "6143" / "t6908_2816" / "bundle"
    assert paths.surrogate == tmp_path / "6143" / "t6908_2816" / "surrogate"
    assert paths.baseline == paths.surrogate / "baseline"
    assert paths.plans == tmp_path / "6143" / "t6908_2816" / "plans"
    assert paths.results == tmp_path / "6143" / "t6908_2816" / "results.json"
    assert paths.tiles_json == tmp_path / "6143" / "tiles.json"


def test_stage_presence_is_read_from_the_files_that_prove_it(tmp_path):
    paths = TilePaths(tmp_path, 6143, Tile(6908, 2816))
    assert paths.stages() == {
        "bundle": False,
        "baseline": False,
        "surrogate": False,
        "model": False,
        "results": False,
    }
    (paths.bundle).mkdir(parents=True)
    (paths.bundle / "provenance.json").write_text("{}")
    paths.baseline.mkdir(parents=True)
    (paths.baseline / "tmrt_daylight.npy").write_bytes(b"")
    (paths.surrogate / "manifest.json").write_text("{}")
    (paths.surrogate / "model.pt").write_bytes(b"")
    assert paths.stages() == {
        "bundle": True,
        "baseline": True,
        "surrogate": True,
        "model": True,
        "results": False,
    }


def test_as_dict_lists_every_path_as_text(tmp_path):
    listed = TilePaths(tmp_path, 6143, Tile(6908, 2816)).as_dict()
    assert listed["tile"] == "t6908_2816"
    assert listed["urban_centre"] == 6143
    assert listed["bundle"].endswith(str(Path("6143") / "t6908_2816" / "bundle"))


def test_tiles_of_an_urban_centre_are_the_directories_that_exist(tmp_path):
    for tile_id in ("t6908_2816", "t6908_2818"):
        (tmp_path / "6143" / tile_id / "bundle").mkdir(parents=True)
    (tmp_path / "6143" / "tiles.json").write_text("{}")
    found = TilePaths.existing(tmp_path, 6143)
    assert [paths.tile.id for paths in found] == ["t6908_2816", "t6908_2818"]
    assert TilePaths.existing(tmp_path, 9999) == []
