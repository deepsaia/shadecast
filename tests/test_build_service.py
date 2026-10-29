"""Building is addressed by city and tile: the densest, named tiles, all, or a selection."""

import pytest
from support.fixtures import fixture_centres
from support.fixtures import fixture_corpus
from support.fixtures import fixture_provenance
from support.fixtures import fixture_tiles
from support.recording_progress import RecordingProgress

from shadecast.service.build_request import BuildRequest
from shadecast.service.build_service import BuildService
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.selection import Selection
from shadecast.service.tile_index import TileIndex
from shadecast.service.unknown_city import UnknownCity
from shadecast.service.unknown_tile import UnknownTile

CALLS: list[tuple[str, str, str]] = []


def _fake_build_tile(city, tile, paths):
    CALLS.append((city.key, tile.id, str(paths.bundle)))
    return fixture_provenance(city.key, tile.id)


def _failing_build_tile(city, tile, paths):
    if tile.id == "t43N_250_2546":
        raise RuntimeError("a source was unreachable")
    return _fake_build_tile(city, tile, paths)


@pytest.fixture
def service(tmp_path) -> BuildService:
    CALLS.clear()
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()),
        fixture_centres,
        TileIndex(tmp_path, fixture_tiles),
        ModelCatalog(tmp_path / "models"),
    )
    return BuildService(catalog, tmp_path, _fake_build_tile)


def _ids(service: BuildService, request: BuildRequest) -> list[str]:
    return [target.tile.id for target in service.targets(request)]


def test_without_tiles_the_densest_tile_of_the_city_is_the_target(service):
    assert _ids(service, BuildRequest(city="ahmedabad")) == ["t43N_249_2547"]


def test_named_tiles_all_tiles_and_selections_are_honored(service):
    assert _ids(service, BuildRequest(city="ahmedabad", tiles="t43N_249_2547,t43N_250_2546")) == [
        "t43N_249_2547",
        "t43N_250_2546",
    ]
    assert len(_ids(service, BuildRequest(city="ahmedabad", tiles="all"))) == 6
    assert len(_ids(service, BuildRequest(city="ahmedabad", tiles=""))) == 6
    assert _ids(service, BuildRequest(city="ahmedabad", densest=2)) == [
        "t43N_249_2547",
        "t43N_250_2547",
    ]
    assert len(_ids(service, BuildRequest(city="ahmedabad", stratified=3))) == 3


def test_every_city_means_the_densest_tile_of_each(service):
    targets = service.targets(BuildRequest(build_all=True))
    assert [target.city.key for target in targets] == ["ahmedabad", "london"]


def test_refusals_name_what_was_wrong(service):
    with pytest.raises(ValueError, match="one city"):
        service.targets(BuildRequest(build_all=True, tiles="t43N_250_2546"))
    with pytest.raises(ValueError, match="city key"):
        service.targets(BuildRequest())
    with pytest.raises(UnknownCity, match="atlantis"):
        service.targets(BuildRequest(city="atlantis"))
    with pytest.raises(UnknownTile, match="6908"):
        service.targets(BuildRequest(city="ahmedabad", tiles="6908"))


def test_build_records_each_tile_and_reports_every_step(tmp_path, service):
    progress = RecordingProgress()
    outcome = service.build(BuildRequest(city="ahmedabad", tiles="t43N_249_2547,t43N_250_2546"), progress)
    assert [built.tile for built in outcome.built] == ["t43N_249_2547", "t43N_250_2546"]
    assert outcome.built[0].bundle == str(tmp_path / "6143" / "t43N_249_2547" / "bundle")
    assert outcome.built[0].tier == "A" and outcome.built[0].buildings == 1234
    assert outcome.failed == [] and outcome.chosen == {"ahmedabad": 2} and outcome.totals == {"ahmedabad": 6}
    assert progress.names("step_started") == ["ahmedabad t43N_249_2547", "ahmedabad t43N_250_2546"]
    assert progress.names("step_done") == ["ahmedabad t43N_249_2547", "ahmedabad t43N_250_2546"]
    assert progress.events[0][0] == "started" and progress.events[-1][0] == "finished"


def test_one_failed_tile_does_not_stop_the_others(tmp_path):
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()),
        fixture_centres,
        TileIndex(tmp_path, fixture_tiles),
        ModelCatalog(tmp_path / "models"),
    )
    service = BuildService(catalog, tmp_path, _failing_build_tile)
    progress = RecordingProgress()
    outcome = service.build(BuildRequest(city="ahmedabad", tiles="t43N_250_2546,t43N_249_2547"), progress)
    assert [built.tile for built in outcome.built] == ["t43N_249_2547"]
    assert outcome.failed == ["ahmedabad t43N_250_2546"]
    assert progress.names("step_failed") == ["ahmedabad t43N_250_2546"]
