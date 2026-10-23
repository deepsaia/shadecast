"""Live dashboard for one tile's physics.

A header with the tile and the engine setup, a status line with the elapsed time, a bar over
the plan with the pace and the time left, sparklines of engine seconds and cooling per
design, a live hardware reading, the designs running now, a table of the last ten finished,
how to stop and resume, and a rolling log box. The box shows warnings and errors always and
the chatty lines only when the command ran with -v. Quiet mode renders nothing and is what
the library and the tests use.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TaskID, TextColumn
from rich.table import Table
from rich.text import Text

from ..hardware import Hardware
from .log_tail import LogTail

BLOCKS = "▁▂▃▄▅▆▇█"
LAST_ROWS = 10
LOG_LINES = 10


def sparkline(values: list[float]) -> str:
    """Eight-level bars for a short series, the way a glance reads a trend."""
    if not values:
        return ""
    low, high = min(values), max(values)
    if high == low:
        return BLOCKS[3] * len(values)
    return "".join(BLOCKS[int((v - low) / (high - low) * (len(BLOCKS) - 1))] for v in values)


def clock(seconds: float) -> str:
    """Hours and minutes, or minutes and seconds under an hour."""
    seconds = max(0, int(seconds))
    if seconds >= 3600:
        return f"{seconds // 3600}h {seconds % 3600 // 60:02d}m"
    return f"{seconds // 60}m {seconds % 60:02d}s"


RUNNING_BAR_WIDTH = 20


def running_bar(share: float) -> str:
    """A thin bar for a share between 0 and 1, the same glyphs as the designs bar."""
    filled = round(min(max(share, 0.0), 1.0) * RUNNING_BAR_WIDTH)
    return "━" * filled + "╺" + "━" * max(0, RUNNING_BAR_WIDTH - filled - 1)


def verbose_logging() -> bool:
    """True when the command ran with -v, which sets the root logger to DEBUG."""
    return logging.getLogger().getEffectiveLevel() <= logging.DEBUG


@dataclass
class GenerationProgress:
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
    running: dict[str, float] = field(default_factory=dict)
    finished: list[dict] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    phase: str = "starting"
    live: Live | None = None
    bar: Progress | None = None
    task: TaskID | None = None
    tail: LogTail | None = None
    saved_handlers: list[logging.Handler] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def quiet(cls) -> GenerationProgress:
        return cls(console=None)

    # --- lifecycle --------------------------------------------------------------------

    def __enter__(self) -> GenerationProgress:
        if self.console is None:
            return self
        self.bar = Progress(
            TextColumn("designs"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TextColumn("{task.fields[pace]}"),
            console=self.console,
            auto_refresh=False,
        )
        # Records go into the rolling box instead of the terminal, so the display stays whole.
        root = logging.getLogger()
        self.saved_handlers = list(root.handlers)
        for handler in self.saved_handlers:
            root.removeHandler(handler)
        self.tail = LogTail(logging.DEBUG if verbose_logging() else logging.WARNING, LOG_LINES)
        root.addHandler(self.tail)
        self.live = Live(
            get_renderable=self.render, console=self.console, refresh_per_second=2, transient=False
        )
        self.live.start()
        return self

    def __exit__(self, exc_type: object, *exc: object) -> None:
        if exc_type is KeyboardInterrupt:
            self.phase = "stopped"
        else:
            self.phase = "failed" if exc_type else "done"
        if self.live is not None:
            self.live.refresh()
            self.live.stop()
        if self.console is None:
            return
        root = logging.getLogger()
        root.handlers.clear()
        for handler in self.saved_handlers:
            root.addHandler(handler)

    # --- events from the generator -------------------------------------------------------

    def start(self, label: str, total: int, done: int) -> None:
        """Open the display: ``done`` designs already exist on disk and count as finished."""
        self.label, self.total, self.done_at_start = label, total, done
        self.phase = "running"
        if self.bar is not None:
            self.task = self.bar.add_task("designs", total=total, completed=done, pace="")

    def baseline_started(self) -> None:
        self.phase = "baseline physics"

    def baseline_done(self, seconds: float) -> None:
        self.baseline_seconds = seconds
        self.phase = "running"

    def baseline_kept_from_disk(self) -> None:
        self.baseline_kept = True

    def design_started(self, name: str) -> None:
        with self.lock:
            self.running[name] = time.time()

    def design_done(self, meta: dict) -> None:
        with self.lock:
            self.running.pop(meta["id"], None)
            self.finished.append(meta)
        self._advance()

    def design_skipped(self, name: str, reason: str) -> None:
        with self.lock:
            self.running.pop(name, None)
            self.skipped.append(f"{name} ({reason})")
        self._advance()

    def design_failed(self, name: str, error: str) -> None:
        with self.lock:
            self.running.pop(name, None)
            self.failed.append(f"{name}: {error}")

    # --- readings ---------------------------------------------------------------------

    def mean_seconds(self) -> float | None:
        seconds = [float(m["engine_seconds"]) for m in self.finished]
        return sum(seconds) / len(seconds) if seconds else None

    def completed(self) -> int:
        return self.done_at_start + len(self.finished) + len(self.skipped)

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
        box = self._log_box()
        if box is not None:
            parts.extend([Text(""), box])
        return Group(*parts)

    def _header(self, hardware: Hardware) -> Text:
        threads = f"{self.threads} threads each" if self.threads else "all threads"
        text = Text()
        text.append(self.label or "tile", style="bold")
        text.append(f"  ·  surrogate for {self.kind}  ·  {self.total} designs")
        text.append(
            f"  ·  engine on {hardware.engine_device}, {self.jobs} at a time, {threads}",
            style="dim",
        )
        return text

    def _status_line(self) -> Text:
        started = datetime.fromtimestamp(self.started_at).strftime("%Y-%m-%d %H:%M")
        text = Text()
        text.append(f"{self.phase:<8}", style="bold green" if self.phase == "done" else "bold")
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
        seconds = [float(m["engine_seconds"]) for m in self.finished]
        cooling = [float(m["mean_response_C"]) for m in self.finished]
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
            if self.phase == "baseline physics"
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
        """One line per running design: elapsed, and a bar against the run's mean so far.

        The engine prints nothing during its main loop, so the bar is elapsed time against
        the mean engine seconds of the designs finished in this run. Until one has finished
        there is nothing to measure against, and the line says so.
        """
        text = Text("running now\n", style="bold")
        with self.lock:
            items = sorted(self.running.items(), key=lambda item: item[1])
        if not items:
            idle = "nothing" if self.phase in ("done", "failed", "stopped") else "waiting"
            text.append(f"  {idle}", style="dim")
            return text
        expected = self.mean_seconds()
        for name, since in items:
            elapsed = time.time() - since
            text.append(f"  {name:<24} {clock(elapsed):>8}  ")
            if expected is None:
                text.append("no finished design to measure against yet\n", style="dim")
                continue
            share = min(elapsed / expected, 0.99)
            text.append(running_bar(share), style="cyan")
            text.append(f"  about {clock(max(0.0, expected - elapsed))} left\n", style="dim")
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
            rows = list(self.finished[-LAST_ROWS:])
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

    def _log_box(self) -> Panel | None:
        if self.tail is None or not self.tail.lines:
            return None
        title = "log" if verbose_logging() else "warnings"
        return Panel(
            Text("\n".join(self.tail.lines), style="dim"),
            title=f"{title}, newest last",
            title_align="left",
            border_style="dim",
        )

    def _advance(self) -> None:
        if self.live is not None:
            self.live.refresh()
