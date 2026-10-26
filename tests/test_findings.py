"""The findings are read from the experiment files and the newest assessed model, never typed in."""

import json
from pathlib import Path

from shadecast.service.findings_report import FindingsReport


def _model(root: Path, tile: str, name: str, created: str, skill: float) -> Path:
    model = root / "tiles" / "6143" / tile / "models" / name
    model.mkdir(parents=True)
    (model / "manifest.json").write_text(json.dumps({"created": created}))
    (model / "assessment.json").write_text(json.dumps({"headline": {"mean_skill": skill}}))
    return model / "assessment.json"


def test_latest_assessment_is_the_most_recently_created(tmp_path):
    _model(tmp_path, "t43N_249_2547", "a", "2026-08-26T10:00:00+00:00", 0.7)
    newest = _model(tmp_path, "t43N_249_2547", "b", "2026-10-23T10:00:00+00:00", 0.8)
    assert FindingsReport(tmp_path).latest_assessment() == newest
    assert FindingsReport(tmp_path).collect().surrogate.get("skill") == 0.8


def test_no_assessed_model_means_a_pending_summary(tmp_path):
    findings = FindingsReport(tmp_path).collect()
    assert findings.surrogate.get("status") == "pending"
    assert findings.factorial.get("status") == "pending"
    assert (
        findings.targeting.get("status") == "pending"
        and findings.channel.get("status") == "pending"
    )


def test_factorial_rows_are_summarized_when_present(tmp_path):
    rows = [
        {
            "city": "ahmedabad",
            "kind": "tree",
            "budget_usd": 1e6,
            "units": 10,
            "exposure_drop_C": 1.0,
            "people": 100,
            "efficiency": 10.0,
        },
        {
            "city": "lagos",
            "kind": "tree",
            "budget_usd": 1e6,
            "units": 12,
            "exposure_drop_C": 2.0,
            "people": 400,
            "efficiency": 20.0,
        },
    ]
    (tmp_path / "factorial.json").write_text(json.dumps(rows))
    factorial = FindingsReport(tmp_path).collect().factorial
    assert factorial.get("status") == "done" and factorial.get("cells") == 2
    assert factorial.get("cities") == ["ahmedabad", "lagos"]
