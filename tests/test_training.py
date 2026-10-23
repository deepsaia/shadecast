"""Training keeps the best epoch by held-out skill and stops when it stops improving. CPU, tiny."""

import numpy as np
import pytest
import torch

from shadecast.surrogate import training
from shadecast.surrogate.patch_set import PatchSet
from shadecast.surrogate.training import evaluate_skill, split_by_city, train
from shadecast.surrogate.training_settings import TrainingSettings
from shadecast.surrogate.training_state import CHECKPOINT_NAME

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


def test_a_city_holdout_matches_every_tile_of_the_city():
    origins = ["ahmedabad:t1/d1", "ahmedabad:t2/d1", "lagos:t9/d1", "rio/d1"]
    _, test_mask = split_by_city(origins, "ahmedabad")
    assert test_mask.tolist() == [True, True, False, False]
    _, one_tile = split_by_city(origins, "ahmedabad:t2")
    assert one_tile.tolist() == [False, True, False, False]
    _, plain = split_by_city(origins, "rio")
    assert plain.tolist() == [False, False, False, True]
    with pytest.raises(ValueError, match="phoenix"):
        split_by_city(origins, "phoenix")


def test_a_checkpoint_is_written_every_epoch_and_removed_when_done(tmp_path):
    out = tmp_path / "model" / "model.pt"
    report = train(_patches(), _settings(epochs=3, patience=10), out_path=out)
    assert report["last_epoch"] == 3 and not report["interrupted"]
    assert not (out.parent / CHECKPOINT_NAME).exists()


def test_an_interrupt_keeps_the_best_weights_and_the_checkpoint(tmp_path, monkeypatch):
    calls = {"n": 0}
    real = training._fit_one_epoch

    def interrupt_on_third(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise KeyboardInterrupt
        return real(*args, **kwargs)

    monkeypatch.setattr(training, "_fit_one_epoch", interrupt_on_third)
    out = tmp_path / "model" / "model.pt"
    report = train(_patches(), _settings(epochs=6, patience=10), out_path=out)
    assert report["interrupted"] and report["last_epoch"] == 2
    assert out.exists() and (out.parent / CHECKPOINT_NAME).exists()
    assert report["best_epoch"] in (1, 2)


def test_training_resumes_from_the_checkpoint(tmp_path, monkeypatch):
    calls = {"n": 0}
    real = training._fit_one_epoch

    def interrupt_on_third(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise KeyboardInterrupt
        return real(*args, **kwargs)

    out = tmp_path / "model" / "model.pt"
    monkeypatch.setattr(training, "_fit_one_epoch", interrupt_on_third)
    train(_patches(), _settings(epochs=5, patience=10), out_path=out)
    monkeypatch.setattr(training, "_fit_one_epoch", real)
    report = train(_patches(), _settings(epochs=5, patience=10), out_path=out)
    assert report["resumed_from_epoch"] == 2
    assert report["last_epoch"] == 5
    assert [step["epoch"] for step in report["history"]] == [1, 2, 3, 4, 5]
    assert not (out.parent / CHECKPOINT_NAME).exists()


def test_a_checkpoint_for_other_data_is_refused(tmp_path, monkeypatch):
    calls = {"n": 0}
    real = training._fit_one_epoch

    def interrupt_on_second(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise KeyboardInterrupt
        return real(*args, **kwargs)

    out = tmp_path / "model" / "model.pt"
    monkeypatch.setattr(training, "_fit_one_epoch", interrupt_on_second)
    train(_patches(), _settings(epochs=4, patience=10), out_path=out)
    monkeypatch.setattr(training, "_fit_one_epoch", real)
    with pytest.raises(ValueError, match="different data"):
        train(_patches(), _settings(epochs=9, patience=10), out_path=out)
