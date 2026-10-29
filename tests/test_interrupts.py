"""Ctrl-C ends a command cleanly: engines stopped, queue cancelled, exit code 130, no traceback."""

import subprocess
import sys

import click
from typer.testing import CliRunner

from shadecast import cli
from shadecast import surrogate_cli
from shadecast.cli import app
from shadecast.corpus import tile_paths
from shadecast.service import simulation_service
from shadecast.service.training_request import TrainingRequest
from shadecast.sim import runner

cli_runner = CliRunner()


def test_running_engines_can_be_stopped():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    runner._RUNNING.add(process)
    try:
        assert runner.stop_running_engines() == 1
        process.wait(timeout=5)
        assert process.returncode != 0
    finally:
        runner._RUNNING.discard(process)
        if process.poll() is None:
            process.kill()


def test_run_registered_returns_a_completed_process():
    completed = runner.run_registered([sys.executable, "-c", "print('hi')"], 10, dict())
    assert completed.returncode == 0 and completed.stdout.strip() == "hi"
    assert not runner._RUNNING


def test_entry_point_turns_an_interrupt_into_exit_130(monkeypatch):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "app", interrupted)
    assert cli.entry() == 130


def test_entry_point_keeps_usage_errors_and_planned_exits(monkeypatch):
    def usage(*args, **kwargs):
        raise click.UsageError("bad")

    monkeypatch.setattr(cli, "app", usage)
    assert cli.entry() == 2

    def planned(*args, **kwargs):
        raise click.exceptions.Exit(3)

    monkeypatch.setattr(cli, "app", planned)
    assert cli.entry() == 3


def test_simulate_stops_with_the_resume_line(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    monkeypatch.setattr(tile_paths, "MODELS_ROOT", tmp_path / "models")
    bundle = tmp_path / "6143" / "t43N_249_2547" / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "provenance.json").write_text('{"city": {"key": "ahmedabad"}, "tile": {"id": "t43N_249_2547"}}')

    def interrupted(bundle_dir, destination, settings, progress):
        progress.started("x", total=17, done=3)
        raise KeyboardInterrupt

    monkeypatch.setattr(simulation_service, "simulate", interrupted)
    result = cli_runner.invoke(app, ["simulate", "treeshade", "ahmedabad", "--jobs", "4"])
    assert result.exit_code == 130
    assert "3 of 17" in result.output
    assert "sdc simulate treeshade ahmedabad --jobs 4" in result.output


def test_train_resume_command_repeats_the_options():
    plain = surrogate_cli.train_resume_command(TrainingRequest(target="savannah"))
    assert plain == "sdc surrogate treeshade train savannah --resume"
    pooled = surrogate_cli.train_resume_command(
        TrainingRequest(pair=["ahmedabad", "x/s=x/b"], holdout_city="rio", channels="base")
    )
    assert pooled == (
        "sdc surrogate treeshade train --pair ahmedabad --pair x/s=x/b --holdout-city rio --channels base --resume"
    )
