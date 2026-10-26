"""The listener that hears everything and shows nothing, for tests and callers that do not care."""

from __future__ import annotations

from collections.abc import Mapping


class NullProgress:
    def started(self, label: str, total: int, done: int) -> None:
        return None

    def phase(self, name: str) -> None:
        return None

    def step_started(self, name: str, detail: Mapping[str, object]) -> None:
        return None

    def step_done(self, name: str, seconds: float, detail: Mapping[str, object]) -> None:
        return None

    def step_skipped(self, name: str, reason: str) -> None:
        return None

    def step_failed(self, name: str, error: str) -> None:
        return None

    def warning(self, message: str) -> None:
        return None

    def finished(self, summary: Mapping[str, object]) -> None:
        return None
