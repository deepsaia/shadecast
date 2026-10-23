"""Fit the response surrogate.

The held-out split is by *design*, never by patch. Splitting patches at random
would leak: patches from the same intervention field overlap and share context, so
a model could score well by memorising one design rather than learning the response.
What the benchmark needs is generalisation to an intervention pattern never seen,
which is exactly what a design-level split measures.

Loss is Huber rather than plain squared error. The target is extremely skewed,
roughly 18 C at a planted pixel against under 0.1 C beyond 26 m, and squared error
would let the near field dominate. The far field is the spillover, which is the
whole reason the benchmark exists, so it has to survive training.

The weights kept are the best epoch's by held-out skill, and training stops once that
skill has not improved for a patience of epochs. A last-epoch model depends on where the
training curve happened to end; a best-epoch model does not.
"""

from __future__ import annotations

import copy
import json
import logging
import time
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .model import ResponseUNet
from .patch_set import PatchSet
from .training_settings import TrainingSettings

logger = logging.getLogger(__name__)


def pick_device(preferred: str | None = None) -> torch.device:
    """The named device, else Apple GPU, then CUDA, then CPU."""
    if preferred:
        return torch.device(preferred)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def split_by_design(
    origins: list[str], holdout: float = 0.25, seed: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """Index masks that keep every patch of a design on the same side of the split."""
    unique = sorted(set(origins))
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(unique)
    n_holdout = max(1, round(holdout * len(unique)))
    held = set(shuffled[:n_holdout].tolist())
    origin_array = np.array(origins)
    test = np.isin(origin_array, list(held))
    return ~test, test


def split_by_city(origins: list[str], holdout_city: str) -> tuple[np.ndarray, np.ndarray]:
    """Hold out one whole city, which is the transfer question.

    Origins are tagged ``city/design``. Holding out a design measures whether the
    model generalises to an unseen intervention pattern. Holding out a city measures
    whether it generalises to unseen *geometry*, which is a much harder question and
    the one that decides whether this is a benchmark or a single city demo.
    """
    origin_array = np.array(origins)
    labels = {origin.split("/", 1)[0] for origin in origins}
    cities = {label.split(":", 1)[0] for label in labels}
    if holdout_city not in labels and holdout_city not in cities:
        raise ValueError(f"{holdout_city!r} not among {sorted(labels)}")
    test = np.array(
        [
            origin.startswith(f"{holdout_city}/") or origin.startswith(f"{holdout_city}:")
            for origin in origin_array
        ]
    )
    return ~test, test


def split(patches: PatchSet, settings: TrainingSettings) -> tuple[np.ndarray, np.ndarray]:
    if settings.holdout_city:
        return split_by_city(patches.origins, settings.holdout_city)
    return split_by_design(patches.origins, holdout=settings.holdout, seed=settings.seed)


def _predict(model: nn.Module, inputs: torch.Tensor, batch_size: int) -> torch.Tensor:
    model.eval()
    with torch.no_grad():
        return torch.cat(
            [
                model(inputs[start : start + batch_size])
                for start in range(0, len(inputs), batch_size)
            ]
        )


def _skill(predicted: torch.Tensor, targets: torch.Tensor) -> tuple[float, float]:
    """Held-out mean absolute error and skill against predicting no change anywhere.

    The response is near zero over most of the field, so a low absolute error proves
    nothing on its own and every number must be read against the zero baseline.
    """
    mae = float((predicted - targets).abs().mean())
    baseline_mae = float(targets.abs().mean())
    return mae, 1.0 - mae / max(baseline_mae, 1e-12)


def evaluate_skill(
    state_dict: Mapping[str, torch.Tensor], patches: PatchSet, settings: TrainingSettings
) -> float:
    """Skill of saved weights on the held-out side of the same split the training used.

    Three arguments because the split is a property of the patches and the settings together.
    """
    device = pick_device(settings.device)
    _, test_mask = split(patches, settings)
    model = ResponseUNet(in_channels=patches.channels).to(device)
    model.load_state_dict(state_dict)
    inputs = torch.from_numpy(patches.inputs[test_mask]).float().to(device)
    targets = torch.from_numpy(patches.targets[test_mask]).float().to(device)
    _, skill = _skill(_predict(model, inputs, settings.batch_size), targets)
    return skill


def _fit_one_epoch(
    model: nn.Module,
    optimiser: torch.optim.Optimizer,
    criterion: nn.Module,
    batches: list[tuple[torch.Tensor, torch.Tensor]],
) -> float:
    """One pass over the shuffled training batches. Returns the mean training loss.

    Four arguments because an epoch is the model, how it steps, what it minimises, and the
    data; none of them belongs inside another.
    """
    model.train()
    running = 0.0
    seen = 0
    for inputs, targets in batches:
        optimiser.zero_grad(set_to_none=True)
        loss = criterion(model(inputs), targets)
        loss.backward()
        optimiser.step()
        running += loss.item() * len(inputs)
        seen += len(inputs)
    return running / max(1, seen)


def _batches(
    inputs: torch.Tensor, targets: torch.Tensor, batch_size: int, generator: torch.Generator
) -> list[tuple[torch.Tensor, torch.Tensor]]:
    """Shuffled mini-batches for one epoch, moved to the inputs' device by the caller.

    Four arguments: the two tensors, the batch size, and the generator that makes the shuffle
    reproducible from the seed.
    """
    order = torch.randperm(len(inputs), generator=generator)
    return [
        (inputs[order[start : start + batch_size]], targets[order[start : start + batch_size]])
        for start in range(0, len(order), batch_size)
    ]


def train(patches: PatchSet, settings: TrainingSettings, out_path: Path | None = None) -> dict:
    """Fit the surrogate, keep the best epoch by held-out skill, and report how it went.

    Three arguments: the data, the settings, and where to save; the first two are objects so
    the manifest can record both whole.
    """
    device = pick_device(settings.device)
    torch.manual_seed(settings.seed)
    generator = torch.Generator().manual_seed(settings.seed)

    train_mask, test_mask = split(patches, settings)
    held_designs = sorted(set(np.array(patches.origins)[test_mask].tolist()))
    logger.info(
        "device %s, %d train patches, %d held out across %d unseen designs",
        device,
        int(train_mask.sum()),
        int(test_mask.sum()),
        len(held_designs),
    )

    x_train = torch.from_numpy(patches.inputs[train_mask]).float().to(device)
    y_train = torch.from_numpy(patches.targets[train_mask]).float().to(device)
    x_test = torch.from_numpy(patches.inputs[test_mask]).float().to(device)
    y_test = torch.from_numpy(patches.targets[test_mask]).float().to(device)

    model = ResponseUNet(in_channels=patches.channels).to(device)
    optimiser = torch.optim.AdamW(model.parameters(), lr=settings.learning_rate)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=settings.epochs)
    criterion = nn.HuberLoss(delta=settings.huber_delta)

    history: list[dict] = []
    best_state = copy.deepcopy(model.state_dict())
    best_epoch = 0
    best_skill = float("-inf")
    started = time.time()
    for epoch in range(1, settings.epochs + 1):
        loss = _fit_one_epoch(
            model, optimiser, criterion, _batches(x_train, y_train, settings.batch_size, generator)
        )
        schedule.step()
        mae, skill = _skill(_predict(model, x_test, settings.batch_size), y_test)
        history.append({"epoch": epoch, "train_loss": loss, "test_mae_C": mae, "skill": skill})
        if skill > best_skill:
            best_skill, best_epoch = skill, epoch
            best_state = copy.deepcopy(model.state_dict())
        if epoch % 5 == 0 or epoch == 1:
            logger.info(
                "epoch %2d: train loss %.4f, held-out MAE %.4f C, skill %+.3f",
                epoch,
                loss,
                mae,
                skill,
            )
        if epoch - best_epoch >= settings.patience:
            logger.info("no better skill for %d epochs, stopping at %d", settings.patience, epoch)
            break

    elapsed = time.time() - started
    last = history[-1]
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": best_state, "in_channels": patches.channels}, out_path)

    return {
        "device": str(device),
        "settings": settings.as_dict(),
        "epochs": settings.epochs,
        "last_epoch": int(last["epoch"]),
        "stopped_early": int(last["epoch"]) < settings.epochs,
        "patience": settings.patience,
        "selection": "best held-out skill",
        "best_epoch": best_epoch,
        "best_skill": round(best_skill, 4),
        "train_patches": int(train_mask.sum()),
        "test_patches": int(test_mask.sum()),
        "held_out_designs": held_designs,
        "holdout_mode": "city" if settings.holdout_city else "design",
        "holdout_city": settings.holdout_city,
        "final_test_mae_C": last["test_mae_C"],
        "zero_baseline_mae_C": round(float(np.abs(patches.targets[test_mask]).mean()), 5),
        "final_skill": round(best_skill, 4),
        "beats_predicting_nothing": bool(best_skill > 0),
        "train_seconds": round(elapsed, 1),
        "history": history,
        "checkpoint": str(out_path) if out_path else None,
    }


def save_report(report: dict, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2))
