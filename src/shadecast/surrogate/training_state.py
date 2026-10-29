"""What a training run has done so far, saved after every epoch so it can continue later.

A checkpoint holds the model, the optimizer and the schedule as they stand, the best weights
seen so far with their epoch and skill, the epoch history, the batch generator's state and
the seconds already spent. Resuming replays none of that: it loads and goes on with the next
epoch, and the batch order from then on is the one the uninterrupted run would have had.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

import torch
from torch import nn

from .trainables import Trainables

CHECKPOINT_NAME = "checkpoint.pt"
# Written before the first epoch with the tiles a run trains on, so an unfinished run has a name.
STARTED_NAME = "started.json"


@dataclass
class TrainingState:
    epoch: int = 0
    history: list[dict] = field(default_factory=list)
    best_state: dict = field(default_factory=dict)
    best_epoch: int = 0
    best_skill: float = float("-inf")
    elapsed_before: float = 0.0  # seconds spent before this resume
    resumed_from_epoch: int = 0

    @classmethod
    def fresh(cls, model: nn.Module) -> TrainingState:
        return cls(best_state=copy.deepcopy(model.state_dict()))

    def record(self, epoch: int, loss: float, mae: float, skill: float, model: nn.Module) -> None:
        """Note an epoch's numbers and keep its weights when they are the best so far."""
        self.epoch = epoch
        self.history.append({"epoch": epoch, "train_loss": loss, "test_mae_C": mae, "skill": skill})
        if skill > self.best_skill:
            self.best_skill, self.best_epoch = skill, epoch
            self.best_state = copy.deepcopy(model.state_dict())

    def save(self, path: Path, trainables: Trainables, fingerprint: dict, elapsed_now: float) -> None:
        """Write everything needed to continue after this epoch. Replaces the previous file."""
        payload = {
            "epoch": self.epoch,
            "history": self.history,
            "best_state": self.best_state,
            "best_epoch": self.best_epoch,
            "best_skill": self.best_skill,
            "elapsed": self.elapsed_before + elapsed_now,
            "fingerprint": fingerprint,
            **trainables.state(),
        }
        tmp = path.with_suffix(".tmp")
        torch.save(payload, tmp)
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path, trainables: Trainables, fingerprint: dict) -> TrainingState:
        """Restore a checkpoint into the trainables; refuse one made with different data."""
        payload = torch.load(path, map_location="cpu", weights_only=True)
        if payload.get("fingerprint") != fingerprint:
            raise ValueError(
                f"{path} was written for different data or settings "
                f"({payload.get('fingerprint')} against {fingerprint}); "
                "remove it to start over"
            )
        trainables.restore(payload)
        return cls(
            epoch=int(payload["epoch"]),
            history=list(payload["history"]),
            best_state=payload["best_state"],
            best_epoch=int(payload["best_epoch"]),
            best_skill=float(payload["best_skill"]),
            elapsed_before=float(payload.get("elapsed", 0.0)),
            resumed_from_epoch=int(payload["epoch"]),
        )
