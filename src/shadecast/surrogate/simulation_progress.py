"""Live dashboard for one tile's physics.

A header with the tile and the engine setup, a status line with the elapsed time, a bar over
the plan with the pace and the time left, sparklines of engine seconds and cooling per
design, a live hardware reading, the designs running now with their engine phase, a table of
the last ten finished, how to stop and resume, and a rolling log box. The box shows warnings
and errors always and the chatty lines only when the command ran with -v. Quiet mode renders
nothing and is what the library and the tests use.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rich.console import Console, Group, RenderableType
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TaskID, TextColumn
from rich.table import Table
from rich.text import Text

from ..hardware import Hardware
from ..surrogate.simulation_events import BASELINE, BASELINE_PHASE
from .engine_phase import design_phase, phase_bar
from .live_display import LiveDisplay, clock, sparkline

LAST_ROWS = 10
logger = logging.getLogger(__name__)


@dataclass
class SimulationProgress:
    console: Console | None
    jobs: int = 1
    threads: int | None = None
    kind: str = "tree"
    resume_command: str = ""
    label: str = ""
    total: int = 0
    done_at_start: int = 0
    started_at: float = field(default_factory=time.time)
    baseline_seconds: float | None = None
    baseline_kept: bool = False
    running: dict[str, tuple[float, Path | None]] = field(default_factory=dict)
    done_designs: list[dict] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    state: str = "starting"
    bar: Progress | None = None
    task: TaskID | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    display: LiveDisplay = field(init=False)

    def __post_init__(self) -> None:
        self.display = LiveDisplay(self.console, self.render)

    @classmethod
    def quiet(cls) -> SimulationProgress:
        return cls(console=None)

    # --- lifecycle --------------------------------------------------------------------

    def __enter__(self) -> SimulationProgress:
        if self.console is not None:
            self.bar = Progress(
                TextColumn("designs"),
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
        else:
            self.state = "failed" if exc_type else "done"
        self.display.stop()

    # --- events from the simulation -------------------------------------------------------

    def started(self, label: str, total: int, done: int) -> None:
        """Open the display: ``done`` designs already exist on disk and count as finished."""
        self.label, self.total, self.done_at_start = label, total, done
        self.state = "running"
        if self.bar is not None:
            self.task = self.bar.add_task("designs", total=total, completed=done, pace="")

    def phase(self, name: str) -> None:
        self.state = name

    def step_started(self, name: str, detail: Mapping[str, object]) -> None:
        target = detail.get("target")
        with self.lock:
            self.running[name] = (time.time(), Path(str(target)) if target else None)

    def step_done(self, name: str, seconds: float, detail: Mapping[str, object]) -> None:
        if name == BASELINE:
            self.baseline_seconds = seconds
            self.state = "running"
            return
        with self.lock:
            self.running.pop(name, None)
            self.done_designs.append(dict(detail))
        self._advance()

    def step_skipped(self, name: str, reason: str) -> None:
        if name == BASELINE:
            self.baseline_kept = True
            return
        with self.lock:
            self.running.pop(name, None)
            self.skipped.append(f"{name} ({reason})")
        self._advance()

    def step_failed(self, name: str, error: str) -> None:
        with self.lock:
            self.running.pop(name, None)
            self.failed.append(f"{name}: {error}")

    def warning(self, message: str) -> None:
        logger.warning(message)

    def finished(self, summary: Mapping[str, object]) -> None:  # noqa: ARG002
        return None

    # --- readings ---------------------------------------------------------------------

    def mean_seconds(self) -> float | None:
        seconds = [float(m["engine_seconds"]) for m in self.done_designs]
        return sum(seconds) / len(seconds) if seconds else None

    def completed(self) -> int:
        return self.done_at_start + len(self.done_designs) + len(self.skipped)

    def remaining_seconds(self) -> float | None:
        mean = self.mean_seconds()
        if mean is None:
            return None
        left = self.total - self.completed()
        return mean * left / max(1, self.jobs)

    # --- rendering --------------------------------------------------------------------

    def render(self) -> RenderableType:
        hardware = Hardware.snapshot()
        parts: list[RenderableType] = [
            self._header(hardware),
            self._status_line(),
            Text(""),
        ]
        if self.bar is not None and self.task is not None:
            self.bar.update(self.task, completed=self.completed(), pace=self._pace())
            parts.append(self.bar)
        parts.extend([Text(""), self._metrics(), self._hardware_line(hardware), Text("")])
        parts.append(self._running_now())
        parts.append(Text(""))
        parts.append(self._last_table())
        if self.failed:
            parts.append(Text(""))
            parts.append(Text("failed: " + "; ".join(self.failed), style="red"))
        parts.extend([Text(""), self._controls()])
        box = self.display.log_box()
        if box is not None:
            parts.extend([Text(""), box])
        return Group(*parts)

    def _header(self, hardware: Hardware) -> Text:
        threads = f"{self.threads} threads each" if self.threads else "all threads"
        text = Text()
        text.append(self.label or "tile", style="bold")
        text.append(f"  ·  {self.kind} physics  ·  {self.total} designs")
        text.append(
            f"  ·  engine on {hardware.engine_device}, {self.jobs} at a time, {threads}",
            style="dim",
        )
        return text

    def _status_line(self) -> Text:
        started = datetime.fromtimestamp(self.started_at).strftime("%Y-%m-%d %H:%M")
        text = Text()
        text.append(f"{self.state:<8}", style="bold green" if self.state == "done" else "bold")
        text.append(f" elapsed {clock(time.time() - self.started_at)}   started {started}")
        if self.done_at_start:
            text.append(
                f"   resumed with {self.done_at_start} of {self.total} on disk", style="dim"
            )
        return text

    def _pace(self) -> str:
        mean = self.mean_seconds()
        if mean is None:
            return "first design running" if self.running else ""
        left = self.remaining_seconds()
        return f"{clock(mean)} per design   about {clock(left or 0)} left"

    def _metrics(self) -> Text:
        seconds = [float(m["engine_seconds"]) for m in self.done_designs]
        cooling = [float(m["mean_response_C"]) for m in self.done_designs]
        text = Text()
        if seconds:
            text.append("engine seconds    ", style="bold")
            text.append(
                f"mean {sum(seconds) / len(seconds):5.0f}   last {seconds[-1]:5.0f}   "
                f"{sparkline(seconds)}  {min(seconds):.0f} → {max(seconds):.0f}\n"
            )
            text.append("cooling at trees  ", style="bold")
            text.append(
                f"mean {sum(cooling) / len(cooling):5.2f} C   last {cooling[-1]:5.2f} C   "
                f"{sparkline(cooling)}  per design mean over planted pixels\n"
            )
        baseline = (
            "kept from disk"
            if self.baseline_kept
            else f"{self.baseline_seconds:.0f} s"
            if self.baseline_seconds is not None
            else "running"
            if self.state == BASELINE_PHASE
            else "pending"
        )
        text.append("baseline          ", style="bold")
        text.append(f"{baseline}   skipped {len(self.skipped)}   failed {len(self.failed)}")
        return text

    def _hardware_line(self, hardware: Hardware) -> Text:
        text = Text()
        text.append("hardware          ", style="bold")
        gpu = "GPU in use" if hardware.engine_device == "cuda" else "GPU unused by the engine"
        text.append(
            f"{hardware.cores} cores · load {hardware.load_1min:.1f} · "
            f"cpu {hardware.cpu_percent:.0f}% · "
            f"mem {hardware.memory_used_gb:.0f}/{hardware.memory_total_gb:.0f} GB · {gpu}"
        )
        return text

    def _running_now(self) -> Text:
        """One line per running design: elapsed time and the engine phase read from its files.

        The engine prints nothing per pixel or per hour and writes its outputs once at the
        end, so the only exact progress is which phase it is in: inputs, sky view factor,
        radiation, outputs. No estimate is shown per design.
        """
        text = Text("running now\n", style="bold")
        with self.lock:
            items = sorted(self.running.items(), key=lambda item: item[1][0])
        if not items:
            idle = "nothing" if self.state in ("done", "failed", "stopped") else "waiting"
            text.append(f"  {idle}", style="dim")
            return text
        for name, (since, target) in items:
            text.append(f"  {name:<24} {clock(time.time() - since):>8}  ")
            phase = design_phase(target) if target is not None else 0
            text.append(phase_bar(phase), style="cyan")
            text.append("\n")
        return text

    def _last_table(self) -> Table:
        table = Table(title=f"last {LAST_ROWS} designs", title_justify="left", title_style="bold")
        for column, justify in (
            ("design", "left"),
            ("family", "left"),
            ("coverage", "right"),
            ("planted px", "right"),
            ("mean C", "right"),
            ("seconds", "right"),
        ):
            table.add_column(column, justify=justify)  # type: ignore[arg-type]
        with self.lock:
            rows = list(self.done_designs[-LAST_ROWS:])
        for meta in rows:
            table.add_row(
                str(meta["id"]),
                str(meta.get("family", "")),
                f"{float(meta.get('coverage', 0)):.3f}",
                f"{int(meta.get('placed_px', 0)):,}",
                f"{float(meta.get('mean_response_C', 0)):.2f}",
                f"{float(meta.get('engine_seconds', 0)):.0f}",
            )
        return table

    def _controls(self) -> Text:
        text = Text()
        text.append("stop    ", style="bold")
        text.append("Ctrl-C: the designs running now finish, the queued ones are cancelled\n")
        text.append("resume  ", style="bold")
        text.append(self.resume_command or "run the same command again", style="cyan")
        text.append("   designs on disk are skipped, the baseline is kept", style="dim")
        return text

    def _advance(self) -> None:
        self.display.refresh()
