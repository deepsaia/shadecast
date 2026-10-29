"""A tile's outcome curves are computed once per model, kept beside the tile, and remade when the model changes."""

import json
from pathlib import Path

import pytest
from support import synthetic_tile
from support.fake_surrogate import FakeSurrogate
from support.fixtures import fixture_centres
from support.fixtures import fixture_corpus
from support.fixtures import fixture_tiles

from shadecast.service.city_catalog import CityCatalog
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.scenario_service import ScenarioService
from shadecast.service.selection import Selection
from shadecast.service.sweep_service import COVERAGES
from shadecast.service.sweep_service import THRESHOLDS
from shadecast.service.sweep_service import SweepService
from shadecast.service.tile_index import TileIndex

NEWER_MODEL = "response-unet-ahmedabad-20261105T090000"


@pytest.fixture
def service(tmp_path) -> SweepService:
    tile = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    synthetic_tile.write_model(tmp_path / "models")
    FakeSurrogate.loads.clear()
    FakeSurrogate.predictions = 0
    models = ModelCatalog(tmp_path / "models")
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()), fixture_centres, TileIndex(tmp_path, fixture_tiles), models
    )
    return SweepService(ScenarioService(catalog, models, FakeSurrogate.load))


def test_the_sweep_runs_every_arrangement_along_the_ladder_at_every_threshold(service):
    sweep = service.sweep("ahmedabad", None)
    assert sweep.fresh and sweep.model_id == synthetic_tile.MODEL_ID
    assert [curve.arrangement for curve in sweep.curves] == ["clustered", "scattered", "corridor"]
    assert sweep.coverages == list(COVERAGES) and sweep.thresholds == list(THRESHOLDS)
    assert all(len(curve.points) == len(COVERAGES) for curve in sweep.curves)
    point = sweep.curves[1].points[-1]  # scattered, all of the plantable ground
    assert len(point.people) == len(THRESHOLDS) and len(point.excess_removed) == len(THRESHOLDS)
    at_45, at_49 = THRESHOLDS.index(45.0), THRESHOLDS.index(49.0)
    assert point.people[at_45] == 0 and point.people[at_49] > 0  # 50 C cooled by 2 C crosses 49, not 45
    assert point.exposure_drop > 0 and point.excess_removed[at_45] > 0
    assert FakeSurrogate.predictions == len(COVERAGES) * 3


def test_the_engine_designs_sit_on_the_same_axes(service):
    sweep = service.sweep("ahmedabad", None)
    assert [design.id for design in sweep.designs] == list(synthetic_tile.PLAN_IDS)
    clustered = sweep.designs[0]
    assert clustered.arrangement == "clustered" and clustered.coverage == pytest.approx(16 / 192, abs=1e-4)
    assert clustered.point.exposure_drop > 0 and len(clustered.point.people) == len(THRESHOLDS)


def test_a_current_sweep_is_read_back_and_a_newer_model_remakes_it(service, tmp_path):
    first = service.sweep("ahmedabad", None)
    predictions = FakeSurrogate.predictions
    again = service.sweep("ahmedabad", None)
    assert not again.fresh and again.model_id == first.model_id and FakeSurrogate.predictions == predictions
    assert (tmp_path / str(synthetic_tile.URBAN_CENTRE) / synthetic_tile.TILE_ID / "derived" / "sweep.json").exists()
    newer = tmp_path / "models" / NEWER_MODEL
    newer.mkdir()
    (newer / "model.pt").write_bytes(b"w2")
    tiles = [f"{synthetic_tile.URBAN_CENTRE}/{synthetic_tile.TILE_ID}"]
    (newer / "manifest.json").write_text(json.dumps({"created": "2026-11-05T09:00:00", "data": {"tiles": tiles}}))
    remade = service.sweep("ahmedabad", None)
    assert remade.fresh and remade.model_id == NEWER_MODEL
    assert FakeSurrogate.predictions == predictions + len(COVERAGES) * 3
    assert Path(FakeSurrogate.loads[-1][0]).parent.name == NEWER_MODEL
