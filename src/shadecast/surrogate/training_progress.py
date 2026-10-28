"""Live dashboard for one training run.

A header with the target and what the trainer says it is doing, a status line with the elapsed
time, a bar over the epochs with the pace and the time left at most, one line each for the
patches, the training loss, the held-out error and the skill with a sparkline over the epochs,
how long the skill has stalled against the patience, a hardware reading, a table of the last
ten epochs with the best one marked, how to stop and resume, and a rolling log box. Quiet mode
renders nothing and is what the tests use.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from rich.console import Console, Group, RenderableType
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TaskID, TextColumn
from rich.table import Table
from rich.text import Text

from ..hardware import Hardware
from .live_display import LiveDisplay, clock, sparkline

logger = logging.getLogger(__name__)

PATCHES = "patches"
LAST_ROWS = 10
BEST = "◀ best"


@dataclass
class TrainingProgress:
    console: Console | None
    patience: int
    kind: str = "tree shade"
    target: str = ""
    resume_command: str = ""
    label: str = ""
    total: int = 0
    done_at_start: int = 0
    started_at: float = field(default_factory=time.time)
    cropped: dict = field(default_factory=dict)  # the patches event, with the seconds it took
    epochs: list[dict] = field(default_factory=list)  # one row per epoch of this run
    state: str = "starting"
    bar: Progress | None = None
    task: TaskID | None = None
    display: LiveDisplay = field(init=False)

    def __post_init__(self) -> None:
        self.display = LiveDisplay(self.console, self.render)

    @classmethod
    def quiet(cls, patience: int = 10) -> TrainingProgress:
        return cls(console=None, patience=patience)

    # --- lifecycle --------------------------------------------------------------------

    def __enter__(self) -> TrainingProgress:
        if self.console is not None:
            self.bar = Progress(
                TextColumn("epochs"),
                BarColumn(bar_width=30),
                MofNCompleteColumn(),
                TextColumn("{task.fields[pace]}"),
                console=self.console,
                auto_refresh=False,
            )
        self.display.start()
        return self

    def __exit__(self, exc_type: object, *exc: object) -> None:
        if exc_type is KeyboardInterrupt:
            self.state = "stopped"
        elif exc_type:
            self.state = "failed"
        elif self.state != "stopped":
            self.state = "done"
        self.display.stop()

    # --- events from the trainer ----------------------------------------------------------

    def started(self, label: str, total: int, done: int) -> None:
        """The epochs begin: ``done`` of ``total`` already ran before a resume."""
        self.label, self.total, self.done_at_start = label, total, done
        self.state = "training"
        if self.bar is not None:
            self.task = self.bar.add_task("epochs", total=total, completed=done, pace="")

    def phase(self, name: str) -> None:
        self.state = name

    def step_started(self, name: str, detail: Mapping[str, object]) -> None:
        return None

    def step_done(self, name: str, seconds: float, detail: Mapping[str, object]) -> None:
        if name == PATCHES:
            self.cropped = {**detail, "seconds": seconds}
            return
        self.epochs.append({**detail, "seconds": seconds})
        self.display.refresh()

    def step_skipped(self, name: str, reason: str) -> None:
        logger.info("%s skipped: %s", name, reason)

    def step_failed(self, name: str, error: str) -> None:
        logger.error("%s failed: %s", name, error)

    def warning(self, message: str) -> None:
        logger.warning(message)

    def finished(self, summary: Mapping[str, object]) -> None:
        self.state = "stopped" if summary.get("interrupted") else "done"

    # --- readings ---------------------------------------------------------------------

    def completed(self) -> int:
        return self.done_at_start + len(self.epochs)

    def best(self) -> dict | None:
        """The epoch of this run with the highest held-out skill, or None before the first."""
        if not self.epochs:
            return None
        return max(self.epochs, key=lambda row: float(str(row.get("skill", 0.0))))

    def stalled(self) -> int:
        """Epochs since the best skill, which patience counts against."""
        best = self.best()
        if best is None:
            return 0
        return int(str(self.epochs[-1].get("epoch", 0))) - int(str(best.get("epoch", 0)))

    def mean_seconds(self) -> float | None:
        seconds = self.series("seconds")
        return sum(seconds) / len(seconds) if seconds else None

    def remaining_seconds(self) -> float | None:
        """Time for the epochs left at the pace so far; patience may stop the run sooner."""
        mean = self.mean_seconds()
        if mean is None:
            return None
        return mean * (self.total - self.completed())

    def series(self, key: str) -> list[float]:
        return [float(str(row.get(key, 0.0))) for row in self.epochs]

    # --- rendering --------------------------------------------------------------------

    def render(self) -> RenderableType:
        parts: list[RenderableType] = [self._header(), self._status_line(), Text("")]
        if self.bar is not None and self.task is not None:
            self.bar.update(self.task, completed=self.completed(), pace=self._pace())
            parts.append(self.bar)
        parts.extend([Text(""), self._readings(), self._hardware_line(Hardware.snapshot())])
        parts.extend([Text(""), self._last_table(), Text(""), self._controls()])
        box = self.display.log_box()
        if box is not None:
            parts.extend([Text(""), box])
        return Group(*parts)

    def _header(self) -> Text:
        text = Text()
        text.append(self.target or "training", style="bold")
        text.append(f"  ·  {self.kind} surrogate")
        if self.label:
            text.append(f"  ·  {self.label}", style="dim")
        return text

    def _status_line(self) -> Text:
        started = datetime.fromtimestamp(self.started_at).strftime("%Y-%m-%d %H:%M")
        text = Text()
        text.append(f"{self.state:<8}", style="bold green" if self.state == "done" else "bold")
        text.append(f" elapsed {clock(time.time() - self.started_at)}   started {started}")
        if self.done_at_start:
            text.append(f"   resumed after epoch {self.done_at_start} of {self.total}", style="dim")
        return text

    def _pace(self) -> str:
        mean = self.mean_seconds()
        if mean is None:
            return "first epoch running" if self.cropped else self.state
        return f"{clock(mean)} per epoch   at most {clock(self.remaining_seconds() or 0)} left"

    def _readings(self) -> Text:
        text = Text()
        if self.cropped:
            text.append("patches           ", style="bold")
            text.append(
                f"{int(str(self.cropped.get('patches', 0))):,} of "
                f"{self.cropped.get('patch_px')} px from {self.cropped.get('designs')} designs "
                f"across {self.cropped.get('tiles')} tile(s), cropped in "
                f"{float(str(self.cropped.get('seconds', 0))):.0f} s\n"
            )
        if not self.epochs:
            text.append("epochs            ", style="bold")
            text.append("none finished yet", style="dim")
            return text
        self._curve(text, "train loss        ", "train_loss", "{:.4f}")
        self._curve(text, "held-out MAE      ", "test_mae_C", "{:.4f} C")
        best = self.best() or {}
        skills = self.series("skill")
        text.append("skill             ", style="bold")
        text.append(
            f"best {float(str(best.get('skill', 0))):+.3f} at epoch {best.get('epoch')}   "
            f"last {skills[-1]:+.3f}   {sparkline(skills)}\n"
        )
        text.append("patience          ", style="bold")
        text.append(f"{self.stalled()} of {self.patience} epochs without a better skill")
        return text

    def _curve(self, text: Text, title: str, key: str, form: str) -> None:
        """One readout line: first and last value of a series and its sparkline.

        Four arguments: the text to extend, the title, which series, and how a value prints.
        """
        values = self.series(key)
        text.append(title, style="bold")
        text.append(
            f"first {form.format(values[0])}   last {form.format(values[-1])}   "
            f"{sparkline(values)}\n"
        )

    def _hardware_line(self, hardware: Hardware) -> Text:
        text = Text()
        text.append("hardware          ", style="bold")
        text.append(
            f"{hardware.cores} cores · load {hardware.load_1min:.1f} · "
            f"cpu {hardware.cpu_percent:.0f}% · "
            f"mem {hardware.memory_used_gb:.0f}/{hardware.memory_total_gb:.0f} GB"
        )
        return text

    def _last_table(self) -> Table:
        table = Table(title=f"last {LAST_ROWS} epochs", title_justify="left", title_style="bold")
        for column, justify in (
            ("epoch", "right"),
            ("train loss", "right"),
            ("held-out MAE C", "right"),
            ("skill", "right"),
            ("seconds", "right"),
            ("", "left"),
        ):
            table.add_column(column, justify=justify)  # type: ignore[arg-type]
        best = self.best() or {}
        for row in self.epochs[-LAST_ROWS:]:
            table.add_row(
                str(row.get("epoch")),
                f"{float(str(row.get('train_loss', 0))):.4f}",
                f"{float(str(row.get('test_mae_C', 0))):.4f}",
                f"{float(str(row.get('skill', 0))):+.3f}",
                f"{float(str(row.get('seconds', 0))):.1f}",
                BEST if row.get("epoch") == best.get("epoch") else "",
            )
        return table

    def _controls(self) -> Text:
        text = Text()
        text.append("stop    ", style="bold")
        text.append("Ctrl-C: the epoch under way is lost, the best weights so far are kept\n")
        text.append("resume  ", style="bold")
        text.append(self.resume_command or "run the same command with --resume", style="cyan")
        text.append("   continues from the checkpoint after the last finished epoch", style="dim")
        return text
