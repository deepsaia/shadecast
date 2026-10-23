"""How many tiles a command wants and by which rule, when it is not naming them."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TileSelection:
    densest: int | None = None  # the K tiles with most residents
    stratified: int | None = None  # K tiles spread over built-fraction terciles

    def __post_init__(self) -> None:
        if self.densest and self.stratified:
            raise ValueError("choose --densest or --stratified, not both")

    def wants(self) -> bool:
        return bool(self.densest or self.stratified)
