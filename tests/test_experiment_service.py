"""The pre-registered experiments run over cities' tiles with a baseline, named by city and tile."""

from pathlib import Path

import pytest
from support import synthetic_tile
from support.fixtures import fixture_centres, fixture_corpus, fixture_tiles
from support.recording_progress import RecordingProgress

from shadecast.service import experiment_service
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.experiment_request import ExperimentRequest
from shadecast.service.experiment_service import ExperimentService
from shadecast.service.missing_stage import MissingStage
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.selection import Selection
from shadecast.service.tile_index import TileIndex

SEEN: list[tuple] = []


def _fake_factorial(cities, out_path):
    SEEN.append(("factorial", cities, Path(out_path)))
    Path(out_path).write_text("[]")
    return [{"city": cities[0][0], "kind": "tree"}, {"city": cities[0][0], "kind": "albedo"}]


def _fake_targeting(cities, out_path, *, budget):
    SEEN.append(("targeting", cities, Path(out_path), budget))
    return {"verdict": {"supported": True}, "rows": [{"city": cities[0][0]}]}


def _fake_channel(cities, out_path, *, budget):
    SEEN.append(("channel", cities, Path(out_path), budget))
    return {"verdict": {"supported": False}, "rows": []}


@pytest.fixture
def service(tmp_path, monkeypatch) -> ExperimentService:
    SEEN.clear()
    monkeypatch.setattr(experiment_service, "run_factorial", _fake_factorial)
    monkeypatch.setattr(experiment_service, "run_targeting", _fake_targeting)
    monkeypatch.setattr(experiment_service, "run_channel", _fake_channel)
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()),
        fixture_centres,
        TileIndex(tmp_path / "tiles", fixture_tiles),
        ModelCatalog(tmp_path / "models"),
    )
    return ExperimentService(catalog, tmp_path)


def _with_baseline(root: Path) -> Path:
    tile = synthetic_tile.write_bundle(root / "tiles")
    synthetic_tile.write_baseline(tile)
    return tile


def test_the_factorial_runs_over_each_city_s_tile_with_a_baseline(tmp_path, service):
    tile = _with_baseline(tmp_path)
    progress = RecordingProgress()
    outcome = service.run(ExperimentRequest(name="factorial", cities=["ahmedabad"]), progress)
    [(name, cities, out)] = SEEN
    assert name == "factorial" and out == tmp_path / "factorial.json"
    assert cities == [(f"ahmedabad-{synthetic_tile.TILE_ID}", tile / "bundle", tile / "surrogate")]
    assert outcome.name == "factorial" and outcome.rows == 2 and outcome.out == str(out)
    assert outcome.verdict == {}
    assert (
        progress.names("phase") == ["factorial over 1 tile"]
        and progress.events[-1][0] == "finished"
    )


def test_targeting_and_channel_carry_their_budget_and_verdict(tmp_path, service):
    _with_baseline(tmp_path)
    targeting = service.run(
        ExperimentRequest(name="targeting", cities=["ahmedabad"], budget=1.0e6), RecordingProgress()
    )
    assert SEEN[-1][0] == "targeting" and SEEN[-1][3] == 1.0e6
    assert targeting.verdict == {"supported": True} and targeting.rows == 1
    channel = service.run(
        ExperimentRequest(name="channel", cities=["ahmedabad"], out=tmp_path / "c.json"),
        RecordingProgress(),
    )
    assert SEEN[-1][2] == tmp_path / "c.json" and channel.verdict == {"supported": False}


def test_a_city_without_a_baseline_and_an_unknown_experiment_are_refused(tmp_path, service):
    with pytest.raises(MissingStage, match="sdc build ahmedabad"):
        service.run(ExperimentRequest(name="factorial", cities=["ahmedabad"]), RecordingProgress())
    synthetic_tile.write_bundle(tmp_path / "tiles")
    with pytest.raises(MissingStage, match="sdc run ahmedabad"):
        service.run(ExperimentRequest(name="factorial", cities=["ahmedabad"]), RecordingProgress())
    _with_baseline(tmp_path)
    with pytest.raises(ValueError, match="nope"):
        service.run(ExperimentRequest(name="nope", cities=["ahmedabad"]), RecordingProgress())
    with pytest.raises(ValueError, match="at least one city"):
        service.run(ExperimentRequest(name="factorial", cities=[]), RecordingProgress())
