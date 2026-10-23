"""The walkthrough reads the newest assessed model from the tile layout."""

import json
from pathlib import Path

from shadecast.dash import findings


def _model(root: Path, tile: str, name: str, created: str, skill: float) -> Path:
    model = root / "6143" / tile / "models" / name
    model.mkdir(parents=True)
    (model / "manifest.json").write_text(json.dumps({"created": created}))
    (model / "assessment.json").write_text(json.dumps({"headline": {"mean_skill": skill}}))
    return model / "assessment.json"


def test_latest_assessment_is_the_most_recently_created(tmp_path):
    _model(tmp_path, "t43N_249_2547", "a", "2026-08-26T10:00:00+00:00", 0.7)
    newest = _model(tmp_path, "t43N_249_2547", "b", "2026-10-23T10:00:00+00:00", 0.8)
    assert findings.latest_assessment(tmp_path) == newest


def test_no_assessed_model_means_a_pending_summary(tmp_path):
    assert findings.latest_assessment(tmp_path) is None
    summary = findings.surrogate_summary(None, tmp_path / "transfer_curve.json")
    assert summary["status"] == "pending"
