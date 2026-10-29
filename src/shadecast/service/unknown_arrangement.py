"""Raised when a scenario names an arrangement the physics never ran designs for."""

from __future__ import annotations


class UnknownArrangement(LookupError):
    def __init__(self, arrangement: str) -> None:
        super().__init__(f"no arrangement {arrangement!r}; choose clustered, scattered or corridor")
        self.arrangement = arrangement
