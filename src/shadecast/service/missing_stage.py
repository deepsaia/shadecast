"""Raised when a tile lacks the stage a question needs; names the command that produces it."""

from __future__ import annotations


class MissingStage(LookupError):
    def __init__(self, stage: str, tile: str, command: str) -> None:
        super().__init__(f"{tile} has no {stage} yet; run '{command}' first")
        self.stage = stage
        self.tile = tile
        self.command = command
