"""Ctrl-C ends a command cleanly: engines stopped, queue cancelled, exit code 130, no traceback."""

import subprocess
import sys

import click
from typer.testing import CliRunner

from shadecast import cli, surrogate_cli
from shadecast.cli import app
from shadecast.corpus import tile_paths
from shadecast.sim import runner
from shadecast.surrogate.training_state import CHECKPOINT_NAME

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


def test_generate_stops_with_the_resume_line(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_paths, "TILES_ROOT", tmp_path)
    bundle = tmp_path / "6143" / "t43N_249_2547" / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "provenance.json").write_text(
        '{"city": {"key": "ahmedabad"}, "tile": {"id": "t43N_249_2547"}}'
    )

    def interrupted(bundle_dir, destination, settings, progress):
        progress.start("x", total=17, done=3)
        raise KeyboardInterrupt

    monkeypatch.setattr(surrogate_cli, "generate", interrupted)
    result = cli_runner.invoke(app, ["surrogate", "generate", "ahmedabad", "--jobs", "4"])
    assert result.exit_code == 130
    assert "3 of 17" in result.output
    assert "sdc surrogate generate ahmedabad --jobs 4" in result.output


def test_unfinished_model_is_the_newest_with_a_checkpoint(tmp_path):
    assert surrogate_cli.unfinished_model(tmp_path / "none") is None
    older = tmp_path / "response-unet-x-20261023T100000"
    newer = tmp_path / "response-unet-x-20261023T110000"
    done = tmp_path / "response-unet-x-20261023T120000"
    for folder in (older, newer, done):
        folder.mkdir()
        (folder / CHECKPOINT_NAME).write_bytes(b"c")
    (done / "manifest.json").write_text("{}")
    assert surrogate_cli.unfinished_model(tmp_path) == newer


def test_train_resume_command_repeats_the_options():
    assert surrogate_cli.train_resume_command("savannah", None, None, None, None, "engine") == (
        "sdc surrogate train savannah --resume"
    )
    assert (
        surrogate_cli.train_resume_command(
            None, None, ["ahmedabad", "x/s=x/b"], None, "rio", "base"
        )
        == "sdc surrogate train --pair ahmedabad --pair x/s=x/b --holdout-city rio --channels base --resume"
    )
