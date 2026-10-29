"""Planning is addressed by city and tile; the service plans, simulates and scores the plan."""

import pytest
from support import synthetic_tile
from support.fixtures import fixture_centres
from support.fixtures import fixture_corpus
from support.fixtures import fixture_tiles
from support.recording_progress import RecordingProgress

from shadecast.service import plan_service
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.missing_stage import MissingStage
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.plan_request import PlanRequest
from shadecast.service.plan_service import PlanService
from shadecast.service.selection import Selection
from shadecast.service.tile_index import TileIndex

SEEN: list[tuple] = []


def _fake_evaluate(bundle, kind="tree", budget_usd=10_000_000.0, work_root=None):
    SEEN.append((bundle, kind, budget_usd))
    return {
        "city": "bundle",
        "tier": "A",
        "design_day": synthetic_tile.DESIGN_DAY,
        "intervention": kind,
        "pixels": 1200,
        "baseline": {"exposure": 50.0, "people_at_risk": 512.0, "cost_usd": 0.0},
        "plan": {"exposure": 48.5, "people_at_risk": 400.0, "cost_usd": 2_000_000.0},
        "benefit": {
            "delta_exposure_C": 1.5,
            "delta_people_at_risk": 112.0,
            "excess_reduced_per_1k_usd": 14.4,
            "cost_usd": 2_000_000.0,
        },
        "tmrt_drop_where_planted_C": 3.1,
        "tmrt_drop_all_outdoor_C": 1.2,
        "spillover_C": 0.4,
        "engine_seconds": {"baseline": 300.0, "plan": 320.0},
    }


@pytest.fixture
def service(tmp_path, monkeypatch) -> PlanService:
    SEEN.clear()
    monkeypatch.setattr(plan_service, "evaluate", _fake_evaluate)
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()),
        fixture_centres,
        TileIndex(tmp_path, fixture_tiles),
        ModelCatalog(tmp_path / "models"),
    )
    return PlanService(catalog)


def test_plan_runs_over_the_densest_built_tile_and_reports_the_headline(tmp_path, service):
    tile = synthetic_tile.write_bundle(tmp_path)
    progress = RecordingProgress()
    outcome = service.plan(PlanRequest(target="ahmedabad", kind="tree", budget_usd=2_000_000), progress)
    assert [(tile / "bundle", "tree", 2_000_000)] == SEEN
    assert outcome.tile == synthetic_tile.TILE_ID and outcome.kind == "tree"
    assert outcome.exposure_drop == 1.5 and outcome.people == 112 and outcome.efficiency == 14.4
    assert outcome.cost_usd == 2_000_000.0 and outcome.pixels == 1200
    assert outcome.engine_seconds == 620.0 and outcome.result["spillover_C"] == 0.4
    assert progress.names("phase") == ["baseline physics, then the plan"]
    assert progress.events[-1][0] == "finished"


def test_plan_without_a_bundle_names_the_build_command(service):
    with pytest.raises(MissingStage, match="sdc build ahmedabad"):
        service.plan(PlanRequest(target="ahmedabad"), RecordingProgress())
