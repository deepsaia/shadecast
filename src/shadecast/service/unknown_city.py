"""Raised when no selected city and no urban centre answers to the text a command named."""

from __future__ import annotations


class UnknownCity(LookupError):
    def __init__(self, text: str, reason: str) -> None:
        super().__init__(f"no city or urban centre {text!r}: {reason}")
        self.text = text
