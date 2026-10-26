"""The baseline physics of a tile runs once through the engine and is kept beside the bundle."""

from pathlib import Path

import pytest
from support import synthetic_tile
from support.fixtures import fixture_centres, fixture_corpus, fixture_tiles
from support.recording_progress import RecordingProgress

from shadecast.service.baseline_request import BaselineRequest
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.engine_service import EngineService
from shadecast.service.missing_stage import MissingStage
from shadecast.service.selection import Selection
from shadecast.service.tile_index import TileIndex
from shadecast.sim.result import RunResult
from shadecast.surrogate import dataset

RUNS: list[tuple[Path, str]] = []


def _fake_run(base_path: Path, date: str, **kwargs) -> RunResult:
    RUNS.append((Path(base_path), date))
    tmrt = Path(base_path) / "output_folder" / "0_0" / "TMRT_0_0.tif"
    synthetic_tile.write_hourly_raster(tmrt)
    return RunResult(base_path=Path(base_path), seconds=12.3, tmrt_path=tmrt, returncode=0)


@pytest.fixture
def service(tmp_path, monkeypatch) -> EngineService:
    RUNS.clear()
    monkeypatch.setattr(dataset, "run", _fake_run)
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()), fixture_centres, TileIndex(tmp_path, fixture_tiles)
    )
    return EngineService(catalog)


def test_the_baseline_runs_once_and_is_kept_the_second_time(tmp_path, service):
    tile = synthetic_tile.write_bundle(tmp_path)
    progress = RecordingProgress()
    first = service.run_baseline(BaselineRequest(target="ahmedabad"), progress)
    assert first.tile == synthetic_tile.TILE_ID and first.kept is False and first.seconds == 12.3
    assert first.design_day == synthetic_tile.DESIGN_DAY
    assert Path(first.destination) == tile / "surrogate" / "baseline"
    assert (tile / "surrogate" / "baseline" / "tmrt_daylight.npy").exists()
    assert [date for _, date in RUNS] == [synthetic_tile.DESIGN_DAY]
    assert "baseline physics" in progress.names("phase") and progress.names("step_done") == [
        "baseline"
    ]
    second = service.run_baseline(BaselineRequest(target="ahmedabad"), RecordingProgress())
    assert second.kept is True and second.seconds is None and len(RUNS) == 1


def test_a_city_without_a_bundle_names_the_build_command(service):
    with pytest.raises(MissingStage, match="sdc build ahmedabad"):
        service.run_baseline(BaselineRequest(target="ahmedabad"), RecordingProgress())
