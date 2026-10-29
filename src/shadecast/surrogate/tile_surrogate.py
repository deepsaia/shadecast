"""One tile's trained response model with its scene loaded, ready to predict any placement.

Loading the weights and reading the scene's rasters costs more than a forward pass. A scenario
simulator asks about the same tile many times in a row, so both are loaded once and kept here.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import torch

from .features import CHANNEL_SETS
from .features import channel_set_for
from .features import select
from .features import stack
from .model import ResponseUNet
from .predict import load
from .predict import predict_field
from .scene import Scene


class TileSurrogate:
    # Three arguments because a prediction needs the network, the fixed layers it conditions on, and
    # the device both live on; none of them belongs inside another.
    def __init__(self, model: ResponseUNet, scene: Scene, device: torch.device) -> None:
        self._model = model
        self._scene = scene
        self._device = device
        self._channels = CHANNEL_SETS[channel_set_for(model.in_channels)]

    @classmethod
    def load(cls, checkpoint: Path, bundle: Path, physics_dir: Path) -> TileSurrogate:
        """The weights at the checkpoint over the bundle and the baseline run beside it.

        Three arguments: the model, and the two directories a scene is read from.
        """
        device = torch.device("cpu")
        return cls(load(checkpoint, device), Scene.load(bundle, physics_dir), device)

    def predict(self, placement: np.ndarray) -> tuple[np.ndarray, float]:
        """The cooling field for one placement, and the seconds the forward pass took."""
        features = select(stack(placement, self._scene), self._channels)
        started = time.perf_counter()
        field = predict_field(self._model, features, self._device)
        return field, time.perf_counter() - started
