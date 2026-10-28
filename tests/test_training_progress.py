"""The training dashboard keeps its readings from the trainer's events and renders them."""

from io import StringIO

import pytest
from rich.console import Console

from shadecast.service.progress_listener import ProgressListener
from shadecast.surrogate.training_progress import TrainingProgress

RESUME = "sdc surrogate treeshade train recife --resume"
LABEL = "6 epochs on cpu · 312 train patches, 96 held out across 4 designs"


def _console() -> Console:
    return Console(file=StringIO(), width=120, force_terminal=False, color_system=None)


def _epoch(progress: TrainingProgress, epoch: int, skill: float, seconds: float) -> None:
    detail = {"epoch": epoch, "train_loss": 1.0 / epoch, "test_mae_C": 0.5, "skill": skill}
    progress.step_done(f"epoch {epoch}", seconds, detail)


def _train(progress: TrainingProgress) -> None:
    progress.phase("cropping patches")
    progress.step_done("patches", 4.2, {"patches": 312, "designs": 17, "tiles": 1, "patch_px": 256})
    progress.started(LABEL, total=6, done=2)
    _epoch(progress, 3, 0.1, 8.0)
    _epoch(progress, 4, 0.3, 9.0)
    _epoch(progress, 5, 0.2, 10.0)


def test_quiet_progress_keeps_its_readings_and_renders_nothing():
    progress = TrainingProgress.quiet(patience=3)
    assert isinstance(progress, ProgressListener)
    with progress:
        _train(progress)
        assert progress.completed() == 5
        assert (progress.best() or {}).get("epoch") == 4 and progress.stalled() == 1
        assert progress.mean_seconds() == 9.0 and progress.remaining_seconds() == 9.0
    assert progress.state == "done" and progress.display.live is None


def test_the_dashboard_shows_the_run_the_best_epoch_the_patience_and_the_resume():
    console = _console()
    progress = TrainingProgress(console, patience=10, target="recife", resume_command=RESUME)
    with progress:
        _train(progress)
    console.print(progress.render())
    shown = console.file.getvalue()
    assert "recife" in shown and "tree shade surrogate" in shown and LABEL in shown
    assert "resumed after epoch 2 of 6" in shown and "5/6" in shown and "at most" in shown
    assert "312 of 256 px from 17 designs across 1 tile(s)" in shown
    assert "best +0.300 at epoch 4" in shown and "1 of 10 epochs without a better skill" in shown
    marked = [line for line in shown.splitlines() if "◀ best" in line]
    assert marked and all(" 4 " in line for line in marked), "only epoch 4 is the best"
    assert RESUME in shown


def test_before_the_first_epoch_the_dashboard_says_what_is_happening():
    console = _console()
    progress = TrainingProgress(console, patience=10)
    with progress:
        progress.phase("cropping patches")
        console.print(progress.render())
        progress.step_done("patches", 1.0, {"patches": 8, "designs": 2, "tiles": 1, "patch_px": 64})
        progress.started(LABEL, total=6, done=0)
        console.print(progress.render())
    shown = console.file.getvalue()
    assert "cropping patches" in shown and "none finished yet" in shown
    assert "first epoch running" in shown and "left" not in shown


def test_an_interrupt_leaves_the_display_stopped():
    progress = TrainingProgress.quiet()
    with pytest.raises(KeyboardInterrupt), progress:
        progress.started(LABEL, total=6, done=0)
        raise KeyboardInterrupt
    assert progress.state == "stopped"
    finished = TrainingProgress.quiet()
    with finished:
        finished.started(LABEL, total=6, done=0)
        finished.finished({"interrupted": True})
    assert finished.state == "stopped"
