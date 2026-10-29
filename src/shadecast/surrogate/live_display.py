"""The live terminal display both dashboards run on, and the readouts they share.

A rich Live redraws a dashboard twice a second while its operation runs. Log records go into a
rolling box inside the display instead of the terminal, so the picture stays whole: the root
logger's handlers are set aside on start and put back on stop. The box shows warnings and
errors always, and every record when the command ran with --verbose. Without a console nothing is
rendered, which is what the library and the tests use.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from rich.console import Console
from rich.console import RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from .log_tail import LogTail

BLOCKS = "▁▂▃▄▅▆▇█"
LOG_LINES = 10
REDRAWS_PER_SECOND = 2


class LiveDisplay:
    """Owns the Live and the log box for one dashboard; the dashboard owns what to show."""

    def __init__(self, console: Console | None, render: Callable[[], RenderableType]) -> None:
        self._console = console
        self._render = render
        self.live: Live | None = None
        self._tail: LogTail | None = None
        self._saved_handlers: list[logging.Handler] = []

    def start(self) -> None:
        """Begin redrawing; from now on log records land in the box, not on the terminal."""
        if self._console is None:
            return
        root = logging.getLogger()
        self._saved_handlers = list(root.handlers)
        for handler in self._saved_handlers:
            root.removeHandler(handler)
        self._tail = LogTail(logging.DEBUG if verbose_logging() else logging.WARNING, LOG_LINES)
        root.addHandler(self._tail)
        self.live = Live(
            get_renderable=self._render,
            console=self._console,
            refresh_per_second=REDRAWS_PER_SECOND,
            transient=False,
        )
        self.live.start()

    def stop(self) -> None:
        """Draw the final state once, stop, and give the terminal its log handlers back."""
        if self.live is not None:
            self.live.refresh()
            self.live.stop()
            self.live = None
        if self._console is None:
            return
        root = logging.getLogger()
        root.handlers.clear()
        for handler in self._saved_handlers:
            root.addHandler(handler)

    def refresh(self) -> None:
        if self.live is not None:
            self.live.refresh()

    def log_box(self) -> Panel | None:
        if self._tail is None or not self._tail.lines:
            return None
        title = "log" if verbose_logging() else "warnings"
        return Panel(
            Text("\n".join(self._tail.lines), style="dim"),
            title=f"{title}, newest last",
            title_align="left",
            border_style="dim",
        )


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


def verbose_logging() -> bool:
    """True when the command ran with --verbose, which sets the root logger to DEBUG."""
    return logging.getLogger().getEffectiveLevel() <= logging.DEBUG
