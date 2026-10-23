"""The dash finds cities in the tile layout first and in the legacy roots after."""

from pathlib import Path

import pytest

from shadecast import cities, dash_cli
from shadecast.cities import City
from shadecast.corpus import tile_paths

AHMEDABAD = City(
    "ahmedabad", 6143, "Ahmedabad", "India", 23.0, 72.6, "BSh", "LM", "South Asia", 7898650, 365
)
LAGOS = City("lagos", 1289, "Lagos", "Nigeria", 6.5, 3.3, "Aw", "LM", "Africa", 12846045, 1199)


def _fixture_corpus(entries=None, centres=None) -> dict[str, City]:
    return {"ahmedabad": AHMEDABAD, "lagos": LAGOS}


def _tile(root: Path, urban_centre: int, tile_id: str) -> Path:
    tile = root / str(urban_centre) / tile_id
    (tile / "bundle").mkdir(parents=True)
    (tile / "bundle" / "provenance.json").write_text("{}")
    (tile / "surrogate" / "baseline").mkdir(parents=True)
    (tile / "surrogate" / "baseline" / "tmrt_daylight.npy").write_bytes(b"")
    return tile


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setattr(cities, "corpus", _fixture_corpus)
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path / "tiles")
    monkeypatch.chdir(tmp_path)


def test_a_city_with_one_tile_keeps_its_key(tmp_path):
    tile = _tile(tmp_path / "tiles", 6143, "t43N_249_2546")
    assert dash_cli.discover() == [("ahmedabad", tile / "bundle", tile / "surrogate")]


def test_a_city_with_several_tiles_is_named_by_key_and_tile(tmp_path):
    _tile(tmp_path / "tiles", 6143, "t43N_249_2546")
    _tile(tmp_path / "tiles", 6143, "t43N_249_2548")
    names = [entry[0] for entry in dash_cli.discover()]
    assert names == ["ahmedabad-t43N_249_2546", "ahmedabad-t43N_249_2548"]


def test_a_tile_without_physics_is_not_shown(tmp_path):
    tile = _tile(tmp_path / "tiles", 6143, "t43N_249_2546")
    (tile / "surrogate" / "baseline" / "tmrt_daylight.npy").unlink()
    assert dash_cli.discover() == []
