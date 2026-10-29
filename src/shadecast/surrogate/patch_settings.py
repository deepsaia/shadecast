"""Everything the patch cropper is told, in one object, so callers pass one thing."""

from __future__ import annotations

from dataclasses import dataclass

from .features import CHANNEL_SETS


@dataclass(frozen=True)
class PatchSettings:
    size: int = 256  # patch side in pixels
    per_entry: int = 24  # patches cropped from each design
    seed: int = 0
    channels: str = "engine"  # a key of features.CHANNEL_SETS

    def __post_init__(self) -> None:
        if self.channels not in CHANNEL_SETS:
            raise ValueError(f"unknown channel set {self.channels!r}; one of {sorted(CHANNEL_SETS)}")

    @property
    def names(self) -> tuple[str, ...]:
        """The channel names this cropper keeps, in stack order."""
        return CHANNEL_SETS[self.channels]
