"""One layout for everything a tile produces, keyed by urban centre id and tile id."""

from pathlib import Path

from shadecast.corpus.tile import Tile
from shadecast.corpus.tile_paths import TilePaths
from shadecast.corpus.tile_stages import TileStages
from shadecast.corpus.utm_zone import UtmZone

TILE = Tile(UtmZone(43, False), 249, 2546)


def test_paths_are_keyed_by_urban_centre_and_tile(tmp_path):
    paths = TilePaths(tmp_path, 6143, TILE)
    assert paths.root == tmp_path / "6143" / "t43N_249_2546"
    assert paths.bundle == tmp_path / "6143" / "t43N_249_2546" / "bundle"
    assert paths.surrogate == tmp_path / "6143" / "t43N_249_2546" / "surrogate"
    assert paths.baseline == paths.surrogate / "baseline"
    assert paths.plans == tmp_path / "6143" / "t43N_249_2546" / "plans"
    assert paths.results == tmp_path / "6143" / "t43N_249_2546" / "results.json"
    assert paths.tiles_json == tmp_path / "6143" / "tiles.json"


def test_stage_presence_is_read_from_the_files_that_prove_it(tmp_path):
    paths = TilePaths(tmp_path, 6143, TILE)
    assert paths.stages() == TileStages()
    (paths.bundle).mkdir(parents=True)
    (paths.bundle / "provenance.json").write_text("{}")
    paths.baseline.mkdir(parents=True)
    (paths.baseline / "tmrt_daylight.npy").write_bytes(b"")
    (paths.surrogate / "manifest.json").write_text("{}")
    assert paths.stages() == TileStages(bundle=True, baseline=True, physics=True)
    assert paths.stages().with_model(True).model is True


def test_as_dict_lists_every_path_as_text(tmp_path):
    listed = TilePaths(tmp_path, 6143, TILE).as_dict()
    assert listed["tile"] == "t43N_249_2546"
    assert listed["urban_centre"] == 6143
    assert listed["bundle"].endswith(str(Path("6143") / "t43N_249_2546" / "bundle"))


def test_tiles_of_an_urban_centre_are_the_directories_that_exist(tmp_path):
    for tile_id in ("t43N_249_2546", "t43N_249_2548"):
        (tmp_path / "6143" / tile_id / "bundle").mkdir(parents=True)
    (tmp_path / "6143" / "tiles.json").write_text("{}")
    found = TilePaths.existing(tmp_path, 6143)
    assert [paths.tile.id for paths in found] == ["t43N_249_2546", "t43N_249_2548"]
    assert TilePaths.existing(tmp_path, 9999) == []


def test_a_record_is_rebuilt_from_a_tile_directory(tmp_path):
    root = tmp_path / "6143" / "t43N_249_2546"
    paths = TilePaths.of_root(root)
    assert paths == TilePaths(tmp_path, 6143, TILE)
    assert paths.root == root
