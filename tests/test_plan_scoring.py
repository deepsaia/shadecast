"""Every design of a known arrangement is scored against doing nothing; probes are not plans."""

import pytest
from support import synthetic_tile

from shadecast.corpus.tile_paths import TilePaths
from shadecast.service.field_store import FieldStore
from shadecast.service.plan_scoring import PlanScoring


@pytest.fixture
def scoring(tmp_path) -> PlanScoring:
    tile = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    return PlanScoring(FieldStore(TilePaths.of_root(tile)))


def test_the_baseline_is_hot_and_everyone_outdoors_is_at_risk(scoring):
    baseline = scoring.baseline()
    assert baseline.exposure == synthetic_tile.BASELINE_C
    assert baseline.at_risk == 512


def test_plans_are_the_known_arrangements_in_order_and_the_probe_is_not_one(scoring):
    plans = scoring.plans()
    assert [plan.arrangement for plan in plans] == ["clustered", "corridor", "scattered"]
    assert [plan.id for plan in plans] == ["clustered_0101", "corridor_0302", "random_uniform_0201"]
    assert [plan.trees for plan in plans] == [16, 4, 8]


def test_cooling_designs_earn_positive_efficiency_and_a_design_that_cools_nothing_earns_none(
    scoring,
):
    by_id = {plan.id: plan for plan in scoring.plans()}
    assert by_id.get("clustered_0101").efficiency > 0
    assert by_id.get("random_uniform_0201").exposure_drop > 0
    assert by_id.get("corridor_0302").efficiency == 0.0
    assert by_id.get("corridor_0302").cost_usd > 0


def test_physics_facts_count_every_design_the_engine_ran(scoring):
    physics = scoring.physics()
    assert physics.designs == 4
    assert physics.engine_minutes == round(sum(synthetic_tile.ENGINE_SECONDS) / 60, 1)
    assert (physics.seconds_per_design_min, physics.seconds_per_design_max) == (90, 360)
