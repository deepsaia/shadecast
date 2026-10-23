"""The four objects a training run mutates, carried together so a checkpoint can save them."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


@dataclass
class Trainables:
    model: nn.Module
    optimiser: torch.optim.Optimizer
    schedule: torch.optim.lr_scheduler.LRScheduler
    generator: torch.Generator

    def state(self) -> dict:
        return {
            "model": self.model.state_dict(),
            "optimiser": self.optimiser.state_dict(),
            "schedule": self.schedule.state_dict(),
            "generator": self.generator.get_state(),
        }

    def restore(self, payload: dict) -> None:
        self.model.load_state_dict(payload["model"])
        self.optimiser.load_state_dict(payload["optimiser"])
        self.schedule.load_state_dict(payload["schedule"])
        self.generator.set_state(payload["generator"])
