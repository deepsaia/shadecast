"""Training keeps the best epoch by held-out skill and stops when it stops improving. CPU, tiny."""

import numpy as np
import pytest
import torch

from shadecast.surrogate.patch_set import PatchSet
from shadecast.surrogate.training import evaluate_skill, train
from shadecast.surrogate.training_settings import TrainingSettings

CHANNELS, SIDE = 7, 32


def _patches(seed: int = 0) -> PatchSet:
    """Twelve patches from four designs whose response is twice the placement channel."""
    rng = np.random.default_rng(seed)
    inputs = rng.random((12, CHANNELS, SIDE, SIDE)).astype("float32")
    inputs[:, 0] = (inputs[:, 0] > 0.9).astype("float32")
    targets = (2.0 * inputs[:, 0])[:, None].astype("float32")
    origins = [f"design_{index // 3}" for index in range(12)]
    return PatchSet(inputs, targets, origins)


def _settings(**overrides) -> TrainingSettings:
    base = {"epochs": 6, "batch_size": 4, "patience": 3, "seed": 0, "device": "cpu"}
    return TrainingSettings(**{**base, **overrides})


def test_report_names_the_best_epoch_and_the_last(tmp_path):
    report = train(_patches(), _settings(), out_path=tmp_path / "model.pt")
    assert report["best_epoch"] <= report["last_epoch"] <= 6
    assert report["best_skill"] >= max(step["skill"] for step in report["history"]) - 1e-9
    assert report["selection"] == "best held-out skill"
    assert report["patience"] == 3


def test_saved_weights_are_the_best_epoch(tmp_path):
    patches = _patches()
    settings = _settings()
    report = train(patches, settings, out_path=tmp_path / "model.pt")
    saved = torch.load(tmp_path / "model.pt", map_location="cpu", weights_only=True)
    skill = evaluate_skill(saved["state_dict"], patches, settings)
    assert skill == pytest.approx(report["best_skill"], abs=1e-4)


def test_training_stops_early_when_skill_stops_improving():
    report = train(_patches(), _settings(epochs=40, patience=2), out_path=None)
    assert report["last_epoch"] < 40
    assert report["stopped_early"]


def test_a_city_holdout_needs_two_cities():
    with pytest.raises(ValueError, match="rio"):
        train(_patches(), _settings(holdout_city="rio"), out_path=None)


def test_settings_are_recorded_in_the_report():
    report = train(_patches(), _settings(learning_rate=1e-3), out_path=None)
    assert report["settings"]["learning_rate"] == 1e-3
    assert report["settings"]["loss"] == "huber"
    assert report["settings"]["huber_delta"] == 1.0
    assert report["device"] == "cpu"
