"""The surrogate commands leave with the codes every command shares."""

from typer.testing import CliRunner

from shadecast.cli import app
from shadecast.service.missing_stage import MissingStage
from shadecast.service.training_service import TrainingService

runner = CliRunner()


def test_train_tells_a_wrong_command_line_from_missing_physics(monkeypatch):
    def refuse(self, request, progress):
        raise ValueError("a city holdout needs at least two cities")

    monkeypatch.setattr(TrainingService, "train", refuse)
    wrong = runner.invoke(app, ["surrogate", "treeshade", "train", "ahmedabad", "--holdout-city", "ahmedabad"])
    assert wrong.exit_code == 2 and "two cities" in wrong.output

    def missing(self, request, progress):
        raise MissingStage("physics", "ahmedabad", "sdc simulate treeshade ahmedabad")

    monkeypatch.setattr(TrainingService, "train", missing)
    result = runner.invoke(app, ["surrogate", "treeshade", "train", "ahmedabad"])
    assert result.exit_code == 1 and "sdc simulate treeshade ahmedabad" in result.output
