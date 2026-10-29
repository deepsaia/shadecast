"""A scenario is answered from the tile's surrogate: levers in, outcomes and the cooling field out."""

import json
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest
from pydantic import ValidationError
from support import synthetic_tile
from support.fixtures import fixture_centres
from support.fixtures import fixture_corpus
from support.fixtures import fixture_tiles

from shadecast.service.city_catalog import CityCatalog
from shadecast.service.missing_stage import MissingStage
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.scenario import Scenario
from shadecast.service.scenario_service import ScenarioService
from shadecast.service.selection import Selection
from shadecast.service.tile_index import TileIndex
from shadecast.service.unknown_arrangement import UnknownArrangement

COOLING_C = 2.0
MODEL_ID = "response-unet-ahmedabad-20261028T154005"
FEASIBLE_PIXELS = synthetic_tile.SIZE**2 - 8 * 8  # the whole tile less the block of buildings


class FakeSurrogate:
    """Cools every planted pixel by a fixed amount and nothing else, and counts its loads."""

    loads: ClassVar[list[tuple[Path, Path, Path]]] = []

    @classmethod
    def load(cls, checkpoint: Path, bundle: Path, physics_dir: Path) -> "FakeSurrogate":
        cls.loads.append((checkpoint, bundle, physics_dir))
        return cls()

    def predict(self, placement: np.ndarray) -> tuple[np.ndarray, float]:
        return placement.astype("float32") * COOLING_C, 0.01


def _tile_on_disk(root: Path) -> Path:
    tile = synthetic_tile.write_bundle(root)
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    return tile


def _model(root: Path) -> Path:
    model = root / "models" / MODEL_ID
    model.mkdir(parents=True)
    (model / "model.pt").write_bytes(b"w")
    tiles = [f"{synthetic_tile.URBAN_CENTRE}/{synthetic_tile.TILE_ID}"]
    (model / "manifest.json").write_text(json.dumps({"created": "2026-10-28T15:40:05", "data": {"tiles": tiles}}))
    return model


def _service(root: Path) -> ScenarioService:
    models = ModelCatalog(root / "models")
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()), fixture_centres, TileIndex(root, fixture_tiles), models
    )
    return ScenarioService(catalog, models, FakeSurrogate.load)


@pytest.fixture
def service(tmp_path) -> ScenarioService:
    _tile_on_disk(tmp_path)
    _model(tmp_path)
    FakeSurrogate.loads.clear()
    return _service(tmp_path)


def test_the_same_levers_give_the_same_placement_and_outcome(service):
    first = service.evaluate(Scenario(target="ahmedabad", arrangement="scattered", coverage=0.1))
    second = service.evaluate(Scenario(target="ahmedabad", arrangement="scattered", coverage=0.1))
    assert np.array_equal(first.placement, second.placement)
    assert first.outcome == second.outcome


def test_trees_go_only_on_feasible_ground_at_the_coverage_asked(service):
    answer = service.evaluate(Scenario(target="ahmedabad", arrangement="scattered", coverage=0.25))
    assert answer.outcome.trees == int(0.25 * FEASIBLE_PIXELS) == 48
    assert not answer.placement[:8, :8].any()
    assert answer.outcome.coverage == 0.25
    assert answer.outcome.tile_fraction == round(48 / synthetic_tile.SIZE**2, 4)


def test_cooling_where_people_live_lowers_exposure_and_the_rest_follows(service):
    answer = service.evaluate(Scenario(target="ahmedabad", arrangement="clustered", coverage=0.25))
    outcome = answer.outcome
    assert (outcome.city, outcome.tile, outcome.model_id) == ("ahmedabad", synthetic_tile.TILE_ID, MODEL_ID)
    assert (outcome.baseline_exposure, outcome.baseline_at_risk) == (synthetic_tile.BASELINE_C, 512)
    assert outcome.exposure_drop > 0 and outcome.excess_removed > 0 and outcome.efficiency > 0
    assert outcome.cost_usd > 0 and outcome.surrogate_seconds == 0.01
    assert np.array_equal(answer.cooling > 0, answer.placement)


def test_a_budget_buys_the_coverage_it_implies(service):
    by_budget = service.evaluate(Scenario(target="ahmedabad", arrangement="scattered", budget_usd=10_000.0))
    assert 0 < by_budget.outcome.cost_usd <= 10_000.0
    by_coverage = service.evaluate(
        Scenario(target="ahmedabad", arrangement="scattered", coverage=by_budget.outcome.coverage)
    )
    assert np.array_equal(by_budget.placement, by_coverage.placement)


def test_a_tile_is_loaded_once_for_any_number_of_scenarios(service):
    for coverage in (0.05, 0.1, 0.2):
        service.evaluate(Scenario(target="ahmedabad", coverage=coverage))
    assert len(FakeSurrogate.loads) == 1
    checkpoint, bundle, physics = FakeSurrogate.loads[0]
    assert (checkpoint.name, bundle.name, physics.name) == ("model.pt", "bundle", "physics")
    assert checkpoint.parent.name == MODEL_ID


def test_only_trees_have_a_surrogate_and_an_arrangement_must_be_known(service):
    with pytest.raises(ValueError, match="no surrogate yet"):
        service.evaluate(Scenario(target="ahmedabad", kind="shade", coverage=0.1))
    with pytest.raises(UnknownArrangement, match="orchard"):
        service.evaluate(Scenario(target="ahmedabad", arrangement="orchard", coverage=0.1))


def test_a_scenario_sets_its_size_with_exactly_one_lever():
    with pytest.raises(ValidationError, match="exactly one"):
        Scenario(target="ahmedabad")
    with pytest.raises(ValidationError, match="exactly one"):
        Scenario(target="ahmedabad", coverage=0.1, budget_usd=5.0)
    with pytest.raises(ValidationError, match="at most 1"):
        Scenario(target="ahmedabad", coverage=1.5)
    with pytest.raises(ValidationError, match="above 0"):
        Scenario(target="ahmedabad", budget_usd=0.0)


def test_a_city_without_a_model_names_the_training_command(tmp_path):
    _tile_on_disk(tmp_path)
    with pytest.raises(MissingStage, match="sdc surrogate treeshade train"):
        _service(tmp_path).evaluate(Scenario(target="ahmedabad", coverage=0.1))
