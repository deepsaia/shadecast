"""The build on the terminal: a spinner while a tile's layers are pulled, a row per bundle built."""

from __future__ import annotations

from collections.abc import Mapping

from rich.console import Console
from rich.status import Status

from .console import add_build_row, build_table


class BuildProgress:
    """A progress listener that keeps the build output the command line always had."""

    def __init__(self, console: Console) -> None:
        self._console = console
        self._table = build_table()
        self._status: Status | None = None

    def started(self, label: str, total: int, done: int) -> None:
        self._status = self._console.status(f"[cyan]{label}[/]")
        self._status.start()

    def phase(self, name: str) -> None:
        if self._status is not None:
            self._status.update(f"[cyan]{name}[/]")

    def step_started(self, name: str, detail: Mapping[str, object]) -> None:
        if self._status is not None:
            self._status.update(f"[cyan]{name}[/]: pulling open layers")

    def step_done(self, name: str, seconds: float, detail: Mapping[str, object]) -> None:
        provenance = detail.get("provenance")
        if isinstance(provenance, dict):
            add_build_row(self._table, name, seconds, provenance)
        pick = f" --tiles {detail.get('tile')}" if detail.get("several") else ""
        city, tile = detail.get("city"), detail.get("tile")
        self._console.print(
            f"[green]{city}[/] {tile}: bundle at {detail.get('bundle')}\n"
            f"  next: sdc surrogate treeshade generate {city}{pick} --jobs 4"
        )

    def step_skipped(self, name: str, reason: str) -> None:
        self._console.print(f"[dim]{name} skipped: {reason}[/]")

    def step_failed(self, name: str, error: str) -> None:
        self._console.print(f"[red]{name} failed:[/] {error}")

    def warning(self, message: str) -> None:
        self._console.print(f"[yellow]{message}[/]")

    def finished(self, summary: Mapping[str, object]) -> None:
        if self._status is not None:
            self._status.stop()
            self._status = None
        self._console.print(self._table)
