"""Raised when no model of the urban centre carries the id a command named."""

from __future__ import annotations


class UnknownModel(LookupError):
    def __init__(self, urban_centre: int, model_id: str) -> None:
        super().__init__(f"urban centre {urban_centre} has no model named {model_id!r}")
        self.model_id = model_id
