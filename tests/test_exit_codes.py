"""Every command leaves the same way: 2 for a wrong command line, 1 for work that could not be done."""

import pytest
import typer
from pydantic import ValidationError

from shadecast import exit_codes
from shadecast.service.missing_stage import MissingStage
from shadecast.service.scenario import Scenario
from shadecast.service.unknown_city import UnknownCity
from shadecast.service.unknown_model import UnknownModel
from shadecast.service.unknown_tile import UnknownTile


def test_a_wrong_command_line_is_2_and_work_that_could_not_be_done_is_1():
    assert exit_codes.exit_code(UnknownCity("atlantis", "no such place")) == 2
    assert exit_codes.exit_code(UnknownTile("6143", "6908")) == 2
    assert exit_codes.exit_code(UnknownModel(6143, "nope")) == 2
    assert exit_codes.exit_code(ValueError("choose --densest or --stratified, not both")) == 2
    assert exit_codes.exit_code(KeyError("no tile 't1_1' in this urban centre")) == 2
    assert exit_codes.exit_code(MissingStage("bundle", "ahmedabad", "sdc build ahmedabad")) == 1
    assert exit_codes.exit_code(RuntimeError("3 designs failed")) == 1
    assert exit_codes.exit_code(FileNotFoundError("no manifest")) == 1


def test_fail_prints_the_message_on_stderr_and_exits_with_the_code(capsys):
    with pytest.raises(typer.Exit) as left:
        exit_codes.fail(MissingStage("bundle", "ahmedabad", "sdc build ahmedabad"))
    assert left.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "run 'sdc build ahmedabad' first" in captured.err


def test_a_key_error_is_printed_without_its_quotes(capsys):
    with pytest.raises(typer.Exit) as left:
        exit_codes.fail(KeyError("no tile 't1_1' in this urban centre"))
    assert left.value.exit_code == 2
    assert capsys.readouterr().err.startswith("no tile 't1_1'")


def test_a_validation_error_is_one_line_without_the_scaffolding():
    with pytest.raises(ValidationError) as caught:
        Scenario(target="ahmedabad")
    assert exit_codes.message(caught.value) == "give exactly one of coverage and budget_usd"
    assert exit_codes.exit_code(caught.value) == 2
