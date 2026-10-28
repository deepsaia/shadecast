"""Assessment finds a city's model and the tile to judge it on, and writes the report beside it."""

import json
from pathlib import Path

import pytest

from shadecast.service import assessment_service
from shadecast.service.assessment_request import AssessmentRequest
from shadecast.service.assessment_service import AssessmentService, assessment_name
from shadecast.service.missing_stage import MissingStage
from shadecast.service.null_progress import NullProgress
from shadecast.service.unknown_model import UnknownModel

CENTRE = 6143
SEEN: list = []


def _bundle(root: Path, tile_id: str) -> Path:
    bundle = root / str(CENTRE) / tile_id / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "provenance.json").write_text(
        json.dumps({"city": {"key": "ahmedabad"}, "tile": {"id": tile_id, "urban_centre": CENTRE}})
    )
    return bundle


def _physics(bundle: Path) -> Path:
    physics = bundle.parent / "physics"
    physics.mkdir()
    (physics / "manifest.json").write_text("{}")
    return physics


def _model(root: Path, tile_id: str, name: str) -> Path:
    model = root / "models" / name
    model.mkdir(parents=True)
    (model / "model.pt").write_bytes(b"w")
    tiles = [{"city": "ahmedabad", "tile": tile_id, "urban_centre": CENTRE}]
    (model / "manifest.json").write_text(json.dumps({"data": {"tiles": tiles}}))
    return model


def _fake_assess(inputs, device=None):
    SEEN.append(inputs)
    return {
        "headline": {
            "mean_skill": 0.73,
            "all_beat_predicting_nothing": True,
            "mean_aggregate_relative_error": 0.03,
        },
        "ranking": {"spearman": 0.9},
        "speed": {"speedup": 1200.0},
    }


@pytest.fixture
def service(tmp_path, monkeypatch) -> AssessmentService:
    SEEN.clear()
    monkeypatch.setattr(assessment_service, "assess", _fake_assess)
    return AssessmentService(tmp_path, tmp_path / "models")


def test_the_newest_model_and_the_densest_tile_with_physics_are_chosen(tmp_path, service):
    bundle = _bundle(tmp_path, "t43N_249_2547")
    physics = _physics(bundle)
    _model(tmp_path, "t43N_249_2547", "response-unet-ahmedabad-20260826T143800")
    newest = _model(tmp_path, "t43N_249_2547", "response-unet-ahmedabad-20261023T121739")
    chosen = service.model_for("ahmedabad", None, None)
    assert chosen == (newest, physics, bundle)
    named = service.model_for("ahmedabad", "response-unet-ahmedabad-20260826T143800", None)
    assert named[0].name == "response-unet-ahmedabad-20260826T143800"
    pooled = tmp_path / "models" / "response-unet-ahmedabad-2tiles-20261024T090000"
    pooled.mkdir(parents=True)
    (pooled / "model.pt").write_bytes(b"w")
    (pooled / "manifest.json").write_text(
        json.dumps(
            {
                "created": "2026-10-24T09:00:00+00:00",
                "data": {"tiles": [{"urban_centre": CENTRE}, {"urban_centre": CENTRE}]},
            }
        )
    )
    assert service.model_for("ahmedabad", None, None)[0] == pooled
    assert assessment_name(pooled, bundle) == "assessment-ahmedabad-t43N_249_2547.json"
    assert assessment_name(newest, bundle) == "assessment.json"


def test_refusals_name_the_training_command_the_unknown_model_and_the_missing_physics(
    tmp_path, service
):
    bundle = _bundle(tmp_path, "t43N_249_2547")
    with pytest.raises(MissingStage, match="sdc simulate treeshade"):
        service.model_for("ahmedabad", None, None)
    _physics(bundle)
    with pytest.raises(MissingStage, match="sdc surrogate treeshade train"):
        service.model_for("ahmedabad", None, None)
    _model(tmp_path, "t43N_249_2547", "response-unet-ahmedabad-20261023T121739")
    with pytest.raises(UnknownModel, match="nope"):
        service.model_for("ahmedabad", "nope", None)
    with pytest.raises(ValueError, match="no simulated physics"):
        service.model_for("ahmedabad", None, "t43N_250_2547")


def test_assess_runs_the_model_on_its_tile_and_writes_the_report_beside_it(tmp_path, service):
    bundle = _bundle(tmp_path, "t43N_249_2547")
    physics = _physics(bundle)
    model = _model(tmp_path, "t43N_249_2547", "response-unet-ahmedabad-20261023T121739")
    outcome = service.assess(
        AssessmentRequest(target="ahmedabad", design=["clustered_0105"]), NullProgress()
    )
    [inputs] = SEEN
    assert (inputs.model_dir, inputs.physics_dir, inputs.bundle, inputs.only) == (
        model,
        physics,
        bundle,
        ["clustered_0105"],
    )
    assert outcome.skill == 0.73 and outcome.beats_nothing is True and outcome.error == 0.03
    assert outcome.spearman == 0.9 and outcome.speedup == 1200.0
    assert Path(outcome.report_path) == model / "assessment.json"
    assert json.loads(Path(outcome.report_path).read_text())["headline"]["mean_skill"] == 0.73


def test_a_model_directory_with_its_tile_is_assessed_as_given(tmp_path, service):
    bundle = _bundle(tmp_path, "t43N_249_2547")
    physics = _physics(bundle)
    model = tmp_path / "elsewhere" / "model"
    model.mkdir(parents=True)
    request = AssessmentRequest(target=str(model), physics_dir=physics, bundle=bundle)
    outcome = service.assess(request, NullProgress())
    assert Path(outcome.model_dir) == model and SEEN[0].bundle == bundle
    with pytest.raises(ValueError, match="PHYSICS_DIR and BUNDLE"):
        service.assess(AssessmentRequest(target=str(model)), NullProgress())
