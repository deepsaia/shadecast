"""Training is addressed by city and tile, or by pairs; the service crops, fits and writes."""

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from shadecast.service import training_service
from shadecast.service.missing_stage import MissingStage
from shadecast.service.null_progress import NullProgress
from shadecast.service.training_request import TrainingRequest
from shadecast.service.training_service import TrainingService
from shadecast.service.training_service import unfinished_model
from shadecast.surrogate.manifest import EPOCHS_FILE
from shadecast.surrogate.training_state import CHECKPOINT_NAME
from shadecast.surrogate.training_state import STARTED_NAME

CENTRE = 6143


def _bundle(root: Path, tile_id: str, key: str = "ahmedabad") -> Path:
    bundle = root / str(CENTRE) / tile_id / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "provenance.json").write_text(
        json.dumps({"city": {"key": key}, "tile": {"id": tile_id, "urban_centre": CENTRE}})
    )
    return bundle


def _physics(bundle: Path) -> Path:
    physics = bundle.parent / "physics"
    (physics / "baseline").mkdir(parents=True)
    (physics / "baseline" / "engine.json").write_text(
        json.dumps({"engine": "solweig-gpu", "version": "solweig_gpu 2.0.0", "seconds": 185.1})
    )
    (physics / "manifest.json").write_text(
        json.dumps(
            {
                "manifest": [
                    {"id": "sparse_probe_0000", "family": "sparse_probe", "engine_seconds": 358.3},
                    {"id": "clustered_0105", "family": "clustered", "engine_seconds": 210.0},
                ]
            }
        )
    )
    return physics


def _service(root: Path) -> TrainingService:
    return TrainingService(root, root / "models")


def test_pairs_accept_keys_paths_and_mixed_pairs(tmp_path):
    service = _service(tmp_path)
    bundle = _bundle(tmp_path, "t43N_249_2547")
    with pytest.raises(MissingStage, match="sdc simulate treeshade ahmedabad"):
        service.pairs_for(TrainingRequest(target="ahmedabad"))
    physics = _physics(bundle)
    assert service.pairs_for(TrainingRequest(target="ahmedabad")) == [(physics, bundle)]
    direct = TrainingRequest(target="a/physics", bundle=Path("a/bundle"))
    assert service.pairs_for(direct) == [(Path("a/physics"), Path("a/bundle"))]
    mixed = service.pairs_for(TrainingRequest(pair=["ahmedabad", "x/s=x/b"]))
    assert mixed == [(physics, bundle), (Path("x/s"), Path("x/b"))]
    second = _bundle(tmp_path, "t43N_250_2547")
    assert service.pairs_for(TrainingRequest(target="ahmedabad")) == [(physics, bundle)]
    with pytest.raises(ValueError, match="has no simulated physics"):
        service.pairs_for(TrainingRequest(target="ahmedabad", tiles="t43N_250_2547"))
    _physics(second)
    both = service.pairs_for(TrainingRequest(target="ahmedabad"))
    assert both == [(physics, bundle), (second.parent / "physics", second)]
    with pytest.raises(ValueError, match="give a city key"):
        service.pairs_for(TrainingRequest())


def test_pairs_follow_a_densest_or_stratified_selection(tmp_path):
    service = _service(tmp_path)
    rows = []
    for tile_id, density, built in (
        ("t43N_249_2547", 9000, 0.9),
        ("t43N_250_2547", 5000, 0.5),
        ("t43N_251_2547", 1000, 0.1),
    ):
        _physics(_bundle(tmp_path, tile_id))
        rows.append(
            {
                "id": tile_id,
                "population_2020": density,
                "density_2020_per_km2": density,
                "built_fraction": built,
            }
        )
    (tmp_path / str(CENTRE) / "tiles.json").write_text(json.dumps({"tiles": rows}))
    densest = service.pairs_for(TrainingRequest(target="ahmedabad", densest=2))
    assert [bundle.parent.name for _, bundle in densest] == ["t43N_249_2547", "t43N_250_2547"]
    spread = service.pairs_for(TrainingRequest(target="ahmedabad", stratified=3))
    assert len(spread) == 3


def _fake_report() -> dict:
    return {
        "device": "cpu",
        "settings": {},
        "epochs": 6,
        "best_epoch": 4,
        "last_epoch": 6,
        "stopped_early": False,
        "interrupted": False,
        "resumed_from_epoch": 0,
        "patience": 3,
        "selection": "best held-out skill",
        "best_skill": 0.71,
        "train_patches": 3,
        "test_patches": 1,
        "held_out_designs": ["clustered_0105"],
        "holdout_mode": "design",
        "holdout_city": None,
        "final_test_mae_C": 0.4,
        "zero_baseline_mae_C": 1.4,
        "final_skill": 0.71,
        "beats_predicting_nothing": True,
        "train_seconds": 12.5,
        "history": [{"epoch": 1, "train_loss": 0.5, "test_mae_C": 0.6, "skill": 0.5}],
        "checkpoint": "model.pt",
    }


def _fake_crop(physics_dir, bundle, settings):
    inputs = np.zeros((4, 7, 8, 8), dtype="float32")
    targets = np.ones((4, 1, 8, 8), dtype="float32")
    return (
        inputs,
        targets,
        ["clustered_0105", "clustered_0105", "sparse_probe_0000", "sparse_probe_0000"],
    )


STARTED: list[dict] = []


def _fake_train(patches, settings, out_path=None, progress=None):
    """Stands in for the trainer and keeps the start record as it stood while training ran."""
    STARTED.append(json.loads((Path(out_path).parent / STARTED_NAME).read_text()))
    Path(out_path).write_bytes(b"weights")
    return _fake_report()


def test_train_crops_fits_and_writes_the_model_its_manifest_and_its_curve(tmp_path, monkeypatch):
    _physics(_bundle(tmp_path, "t43N_249_2547"))
    monkeypatch.setattr(training_service, "crop_batch", _fake_crop)
    monkeypatch.setattr(training_service, "train", _fake_train)
    outcome = _service(tmp_path).train(TrainingRequest(target="ahmedabad", epochs=6), NullProgress())
    destination = Path(outcome.destination)
    assert destination.parent == tmp_path / "models"
    started = STARTED[-1]
    assert started["cities"] == ["ahmedabad"] and started["tiles"] == [f"{CENTRE}/t43N_249_2547"]
    assert not (destination / STARTED_NAME).exists(), "the manifest replaces the start record"
    assert destination.name.startswith("response-unet-ahmedabad-")
    assert (destination / "model.pt").exists() and not (destination / "training_report.json").exists()
    written = json.loads((destination / "manifest.json").read_text())
    assert written["data"]["tiles"] == [f"{CENTRE}/t43N_249_2547"]
    assert written["data"]["patch_px"] == 256 and written["training"]["best_epoch"] == 4
    with (destination / EPOCHS_FILE).open() as handle:
        assert [row["epoch"] for row in csv.DictReader(handle)] == ["1"]
    assert outcome.patches == 4 and outcome.designs == 2 and outcome.cities == 1
    assert outcome.skill == 0.71 and outcome.beats_nothing is True and outcome.interrupted is False


def test_resume_continues_the_newest_unfinished_model(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, "t43N_249_2547")
    _physics(bundle)
    unfinished = tmp_path / "models" / "response-unet-ahmedabad-20261023T100000"
    unfinished.mkdir(parents=True)
    (unfinished / CHECKPOINT_NAME).write_bytes(b"c")
    monkeypatch.setattr(training_service, "crop_batch", _fake_crop)
    monkeypatch.setattr(training_service, "train", _fake_train)
    outcome = _service(tmp_path).train(TrainingRequest(target="ahmedabad", resume=True), NullProgress())
    assert Path(outcome.destination) == unfinished and outcome.resumed is True


def test_resume_with_nothing_unfinished_and_bad_settings_are_refused(tmp_path, monkeypatch):
    _physics(_bundle(tmp_path, "t43N_249_2547"))
    monkeypatch.setattr(training_service, "crop_batch", _fake_crop)
    service = _service(tmp_path)
    with pytest.raises(ValueError, match="nothing to resume"):
        service.train(TrainingRequest(target="ahmedabad", resume=True), NullProgress())
    with pytest.raises(ValueError, match="two cities"):
        service.train(TrainingRequest(target="ahmedabad", holdout_city="rio"), NullProgress())
    with pytest.raises(ValueError, match="channels"):
        service.train(TrainingRequest(target="ahmedabad", channels="nope"), NullProgress())


def test_unfinished_model_is_the_newest_with_a_checkpoint(tmp_path):
    assert unfinished_model(tmp_path / "none") is None
    older = tmp_path / "response-unet-x-20261023T100000"
    newer = tmp_path / "response-unet-x-20261023T110000"
    done = tmp_path / "response-unet-x-20261023T120000"
    for folder in (older, newer, done):
        folder.mkdir()
        (folder / CHECKPOINT_NAME).write_bytes(b"c")
    (done / "manifest.json").write_text("{}")
    assert unfinished_model(tmp_path) == newer
