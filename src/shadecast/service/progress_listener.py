"""What a long operation reports to while it runs, in one vocabulary for every operation.

The command line passes a dashboard, tests pass the null listener, and a job endpoint will pass
an event stream. An operation never knows which. Each step is one unit of the operation's work:
a design through the engine, an epoch of training, a tile built. A phase names what the
operation is doing between steps.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from typing import runtime_checkable


@runtime_checkable
class ProgressListener(Protocol):
    def started(self, label: str, total: int, done: int) -> None:
        """The operation begins: ``done`` of ``total`` steps already exist and count as finished."""

    def phase(self, name: str) -> None:
        """The operation moves into a named phase that is not itself a counted step."""

    def step_started(self, name: str, detail: Mapping[str, object]) -> None: ...

    def step_done(self, name: str, seconds: float, detail: Mapping[str, object]) -> None: ...

    def step_skipped(self, name: str, reason: str) -> None: ...

    def step_failed(self, name: str, error: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def finished(self, summary: Mapping[str, object]) -> None: ...
