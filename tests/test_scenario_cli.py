"""The scenario command moves the levers from the terminal and answers as a table or as JSON."""

import json

import numpy as np
import pytest
from typer.testing import CliRunner

from shadecast.cli import app
from shadecast.service.missing_stage import MissingStage
from shadecast.service.scenario import Scenario
from shadecast.service.scenario_answer import ScenarioAnswer
from shadecast.service.scenario_outcome import ScenarioOutcome
from shadecast.service.scenario_service import ScenarioService

runner = CliRunner()
ASKED: list[Scenario] = []


def _answer(asked: Scenario) -> ScenarioAnswer:
    outcome = ScenarioOutcome(
        city="ahmedabad",
        tile="t43N_249_2547",
        model_id="response-unet-ahmedabad-20261028T154005",
        kind=asked.kind,
        arrangement=asked.arrangement,
        coverage=0.05,
        tile_fraction=0.034,
        trees=34028,
        cost_usd=2_980_000.0,
        unit_cost=asked.unit_cost or 40.0,
        maintenance=asked.maintenance if asked.maintenance is not None else 0.08,
        threshold=asked.threshold if asked.threshold is not None else 45.0,
        baseline_exposure=58.68,
        baseline_at_risk=78568,
        exposure_drop=3.06,
        excess_removed=306_000.0,
        people=1258,
        equity_gap_change=-0.12,
        efficiency=102.99,
        surrogate_seconds=0.54,
    )
    return ScenarioAnswer(outcome, np.zeros((2, 2), dtype="float32"), np.zeros((2, 2), dtype=bool))


@pytest.fixture
def evaluated(monkeypatch):
    ASKED.clear()

    def fake_evaluate(self, asked: Scenario) -> ScenarioAnswer:
        ASKED.append(asked)
        return _answer(asked)

    monkeypatch.setattr(ScenarioService, "evaluate", fake_evaluate)


def test_the_command_answers_as_json_and_as_a_table(evaluated):
    result = runner.invoke(
        app, ["scenario", "ahmedabad", "--arrangement", "scattered", "--coverage", "0.05", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert (payload["arrangement"], payload["trees"], payload["exposure_drop"]) == ("scattered", 34028, 3.06)
    assert (ASKED[0].target, ASKED[0].coverage, ASKED[0].budget_usd) == ("ahmedabad", 0.05, None)
    table = runner.invoke(
        app,
        [
            "scenario",
            "ahmedabad",
            "--budget",
            "5000000",
            "--tile",
            "t43N_249_2547",
            "--unit-cost",
            "80",
            "--threshold",
            "50",
        ],
    )
    assert table.exit_code == 0, table.output
    assert "exposure drop" in table.stdout and "3.06 C" in table.stdout and "80 USD per m2" in table.stdout
    assert "people moved below 50 C" in table.stdout
    assert (ASKED[1].budget_usd, ASKED[1].tile, ASKED[1].unit_cost, ASKED[1].threshold) == (
        5_000_000.0,
        "t43N_249_2547",
        80.0,
        50.0,
    )


def test_wrong_levers_leave_with_2_and_one_line(evaluated):
    neither = runner.invoke(app, ["scenario", "ahmedabad"])
    assert neither.exit_code == 2 and "exactly one of coverage and budget_usd" in neither.output
    too_much = runner.invoke(app, ["scenario", "ahmedabad", "--coverage", "1.5"])
    assert too_much.exit_code == 2 and "at most 1" in too_much.output
    assert ASKED == []


def test_a_city_without_a_model_leaves_with_1_and_the_training_command(monkeypatch):
    def missing(self, asked: Scenario) -> ScenarioAnswer:
        raise MissingStage("model", "urban centre 6143", "sdc surrogate treeshade train ahmedabad")

    monkeypatch.setattr(ScenarioService, "evaluate", missing)
    result = runner.invoke(app, ["scenario", "ahmedabad", "--coverage", "0.1"])
    assert result.exit_code == 1 and "sdc surrogate treeshade train" in result.output
