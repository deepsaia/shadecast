"""The tiles file of an urban centre is read when present and described once when it is not."""

import json

import pytest
from support.fixtures import fixture_centres, fixture_tiles

from shadecast.service.tile_index import TileIndex

AHMEDABAD = fixture_centres().by_id(6143)


class RecordingDescribe:
    """A describe callable that counts its calls and answers the fixture tiles."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, centre: object) -> list[dict]:
        self.calls += 1
        return fixture_tiles(centre)


def _refuse(centre: object) -> list[dict]:
    raise AssertionError("tiles were described although tiles.json exists")


def test_the_file_is_keyed_by_urban_centre_id(tmp_path):
    assert TileIndex(tmp_path, _refuse).path(AHMEDABAD) == tmp_path / "6143" / "tiles.json"


def test_an_absent_file_is_described_and_written_once(tmp_path):
    describe = RecordingDescribe()
    index = TileIndex(tmp_path, describe)
    first = index.read_or_describe(AHMEDABAD)
    second = index.read_or_describe(AHMEDABAD)
    assert describe.calls == 1
    assert first == second
    assert first.get("count") == len(fixture_tiles())
    assert first.get("urban_centre", {}).get("id") == 6143
    assert json.loads((tmp_path / "6143" / "tiles.json").read_text()) == first


def test_a_present_file_is_read_without_describing(tmp_path):
    path = tmp_path / "6143" / "tiles.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"count": 1, "tiles": [{"id": "t43N_249_2547"}]}))
    assert TileIndex(tmp_path, _refuse).read_or_describe(AHMEDABAD).get("count") == 1


def test_refresh_describes_again_and_overwrites(tmp_path):
    describe = RecordingDescribe()
    index = TileIndex(tmp_path, describe)
    index.read_or_describe(AHMEDABAD)
    refreshed = index.describe_and_write(AHMEDABAD)
    assert describe.calls == 2
    assert json.loads(index.path(AHMEDABAD).read_text()) == refreshed


def test_a_centre_without_tiles_is_refused(tmp_path):
    index = TileIndex(tmp_path, lambda centre: [])
    with pytest.raises(ValueError, match="6143"):
        index.read_or_describe(AHMEDABAD)
