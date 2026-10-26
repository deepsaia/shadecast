"""Raised when no surrogate channel carries the key a command or a route named."""

from __future__ import annotations


class UnknownChannel(LookupError):
    def __init__(self, key: str, known: list[str]) -> None:
        super().__init__(f"no surrogate channel {key!r}; one of {', '.join(known)}")
        self.key = key
