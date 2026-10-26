"""The training run on the terminal: a spinner for each phase and a line every fifth epoch."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from rich.console import Console
from rich.status import Status

logger = logging.getLogger(__name__)

PATCHES = "patches"
EVERY = 5


class TrainingProgress:
    """A progress listener that keeps the training output the command line always had."""

    def __init__(self, console: Console) -> None:
        self._console = console
        self._status: Status | None = None

    def started(self, label: str, total: int, done: int) -> None:
        self._stop()
        if done:
            self._console.print(f"[dim]resuming after epoch {done} of {total}[/]")

    def phase(self, name: str) -> None:
        self._stop()
        self._status = self._console.status(f"[cyan]{name}[/]")
        self._status.start()

    def step_started(self, name: str, detail: Mapping[str, object]) -> None:
        return None

    def step_done(self, name: str, seconds: float, detail: Mapping[str, object]) -> None:
        if name == PATCHES:
            self._stop()
            self._console.print(
                f"{int(str(detail.get('patches', 0))):,} patches of {detail.get('patch_px')}px "
                f"from {detail.get('designs')} designs across {detail.get('cities')} cities "
                f"in {seconds:.1f}s"
            )
            return
        epoch = detail.get("epoch")
        if isinstance(epoch, int) and (epoch % EVERY == 0 or epoch == 1):
            logger.info(
                "epoch %2d: train loss %.4f, held-out MAE %.4f C, skill %+.3f",
                epoch,
                float(str(detail.get("train_loss", 0.0))),
                float(str(detail.get("test_mae_C", 0.0))),
                float(str(detail.get("skill", 0.0))),
            )

    def step_skipped(self, name: str, reason: str) -> None:
        self._console.print(f"[dim]{name} skipped: {reason}[/]")

    def step_failed(self, name: str, error: str) -> None:
        self._console.print(f"[red]{name} failed: {error}[/]")

    def warning(self, message: str) -> None:
        self._console.print(f"[yellow]{message}[/]")

    def finished(self, summary: Mapping[str, object]) -> None:
        self._stop()

    def _stop(self) -> None:
        if self._status is not None:
            self._status.stop()
            self._status = None
