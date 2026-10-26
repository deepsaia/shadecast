"""A progress listener that keeps every event, so a test can say what an operation reported."""

from __future__ import annotations

from collections.abc import Mapping


class RecordingProgress:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def started(self, label: str, total: int, done: int) -> None:
        self.events.append(("started", label, total, done))

    def phase(self, name: str) -> None:
        self.events.append(("phase", name))

    def step_started(self, name: str, detail: Mapping[str, object]) -> None:
        self.events.append(("step_started", name, dict(detail)))

    def step_done(self, name: str, seconds: float, detail: Mapping[str, object]) -> None:
        self.events.append(("step_done", name, dict(detail)))

    def step_skipped(self, name: str, reason: str) -> None:
        self.events.append(("step_skipped", name, reason))

    def step_failed(self, name: str, error: str) -> None:
        self.events.append(("step_failed", name, error))

    def warning(self, message: str) -> None:
        self.events.append(("warning", message))

    def finished(self, summary: Mapping[str, object]) -> None:
        self.events.append(("finished", dict(summary)))

    def names(self, kind: str) -> list[str]:
        return [event[1] for event in self.events if event[0] == kind]
