"""The training patches: inputs, targets, and the design each patch came from."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PatchSet:
    inputs: np.ndarray  # (N, channels, side, side)
    targets: np.ndarray  # (N, 1, side, side)
    origins: list[str]  # design id per patch, prefixed city/ when several cities are mixed

    def __len__(self) -> int:
        return len(self.origins)

    @property
    def channels(self) -> int:
        return int(self.inputs.shape[1])
