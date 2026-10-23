"""Everything a training run is told, in one object, so a manifest can record it whole."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TrainingSettings:
    epochs: int = 30
    batch_size: int = 8
    learning_rate: float = 2e-3
    holdout: float = 0.25  # share of designs held out, when no city is
    holdout_city: str | None = None
    seed: int = 0
    patience: int = 10  # epochs without a better held-out skill before training stops
    device: str | None = None  # None picks the best available
    loss: str = "huber"
    huber_delta: float = 1.0
    channels: str = "engine"  # a key of features.CHANNEL_SETS, so the manifest lists the channels

    def as_dict(self) -> dict:
        return asdict(self)
