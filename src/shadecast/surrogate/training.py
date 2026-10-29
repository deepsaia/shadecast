"""Fit the response surrogate.

The held-out split is by *design*, never by patch. Splitting patches at random
would leak: patches from the same intervention field overlap and share context, so
a model could score well by memorising one design rather than learning the response.
What the simulator needs is generalisation to an intervention pattern never seen,
which is exactly what a design-level split measures.

Loss is Huber rather than plain squared error. The target is extremely skewed,
roughly 18 C at a planted pixel against under 0.1 C beyond 26 m, and squared error
would let the near field dominate. The far field is the spillover, which is the
whole reason the simulator exists, so it has to survive training.

The weights kept are the best epoch's by held-out skill, and training stops once that
skill has not improved for a patience of epochs. A last-epoch model depends on where the
training curve happened to end; a best-epoch model does not.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import torch
from torch import nn

from ..service.null_progress import NullProgress
from ..service.progress_listener import ProgressListener
from .model import ResponseUNet
from .patch_set import PatchSet
from .trainables import Trainables
from .training_settings import TrainingSettings
from .training_state import CHECKPOINT_NAME
from .training_state import TrainingState

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


def split_by_design(origins: list[str], holdout: float = 0.25, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
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
    the one that decides whether this is a simulator for any city or a single city demo.
    """
    origin_array = np.array(origins)
    labels = {origin.split("/", 1)[0] for origin in origins}
    cities = {label.split(":", 1)[0] for label in labels}
    if holdout_city not in labels and holdout_city not in cities:
        raise ValueError(f"{holdout_city!r} not among {sorted(labels)}")
    test = np.array(
        [origin.startswith(f"{holdout_city}/") or origin.startswith(f"{holdout_city}:") for origin in origin_array]
    )
    return ~test, test


def split(patches: PatchSet, settings: TrainingSettings) -> tuple[np.ndarray, np.ndarray]:
    if settings.holdout_city:
        return split_by_city(patches.origins, settings.holdout_city)
    return split_by_design(patches.origins, holdout=settings.holdout, seed=settings.seed)


def _predict(model: nn.Module, inputs: torch.Tensor, batch_size: int) -> torch.Tensor:
    model.eval()
    with torch.no_grad():
        return torch.cat([model(inputs[start : start + batch_size]) for start in range(0, len(inputs), batch_size)])


def _skill(predicted: torch.Tensor, targets: torch.Tensor) -> tuple[float, float]:
    """Held-out mean absolute error and skill against predicting no change anywhere.

    The response is near zero over most of the field, so a low absolute error proves
    nothing on its own and every number must be read against the zero baseline.
    """
    mae = float((predicted - targets).abs().mean())
    baseline_mae = float(targets.abs().mean())
    return mae, 1.0 - mae / max(baseline_mae, 1e-12)


def evaluate_skill(state_dict: Mapping[str, torch.Tensor], patches: PatchSet, settings: TrainingSettings) -> float:
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


def train(
    patches: PatchSet,
    settings: TrainingSettings,
    out_path: Path | None = None,
    progress: ProgressListener | None = None,
) -> dict:
    """Fit the surrogate, keep the best epoch by held-out skill, and report how it went.

    Four arguments: the data, the settings, where to save, and who to tell; the first two are
    objects so the manifest can record both whole.
    """
    listener = progress if progress is not None else NullProgress()
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

    checkpoint = Path(out_path).parent / CHECKPOINT_NAME if out_path is not None else None
    fingerprint = {
        "channels": patches.channels,
        "patches": len(patches),
        "seed": settings.seed,
        "epochs": settings.epochs,
    }
    trainables = Trainables(model, optimiser, schedule, generator)
    state = _fresh_or_resumed(checkpoint, trainables, fingerprint)
    listener.started(
        f"{settings.epochs} epochs on {device} · {int(train_mask.sum())} train patches, "
        f"{int(test_mask.sum())} held out across {len(held_designs)} designs",
        settings.epochs,
        state.epoch,
    )

    started = time.time()
    interrupted = False
    try:
        for epoch in range(state.epoch + 1, settings.epochs + 1):
            epoch_started = time.time()
            loss = _fit_one_epoch(
                model,
                optimiser,
                criterion,
                _batches(x_train, y_train, settings.batch_size, generator),
            )
            schedule.step()
            mae, skill = _skill(_predict(model, x_test, settings.batch_size), y_test)
            state.record(epoch, loss, mae, skill, model)
            listener.step_done(
                f"epoch {epoch}",
                round(time.time() - epoch_started, 1),
                {"epoch": epoch, "train_loss": loss, "test_mae_C": mae, "skill": skill},
            )
            if checkpoint is not None:
                state.save(checkpoint, trainables, fingerprint, time.time() - started)
            if epoch - state.best_epoch >= settings.patience:
                logger.info("no better skill for %d epochs, stopping at %d", settings.patience, epoch)
                break
    except KeyboardInterrupt:
        # The epoch under way is lost; everything before it is on disk and the best weights
        # so far are kept. The caller says how to resume.
        if not state.history:
            raise
        interrupted = True
        logger.warning("interrupted after epoch %d; keeping the best weights so far", state.epoch)
        listener.warning(f"interrupted after epoch {state.epoch}; keeping the best weights so far")

    elapsed = state.elapsed_before + (time.time() - started)
    last = state.history[-1]
    _save_best(out_path, state, patches.channels)
    if checkpoint is not None and not interrupted:
        checkpoint.unlink(missing_ok=True)

    report = {
        "device": str(device),
        "settings": settings.as_dict(),
        "epochs": settings.epochs,
        "last_epoch": int(last["epoch"]),
        "stopped_early": int(last["epoch"]) < settings.epochs and not interrupted,
        "interrupted": interrupted,
        "resumed_from_epoch": state.resumed_from_epoch,
        "patience": settings.patience,
        "selection": "best held-out skill",
        "best_epoch": state.best_epoch,
        "best_skill": round(state.best_skill, 4),
        "train_patches": int(train_mask.sum()),
        "test_patches": int(test_mask.sum()),
        "held_out_designs": held_designs,
        "holdout_mode": "city" if settings.holdout_city else "design",
        "holdout_city": settings.holdout_city,
        "final_test_mae_C": last["test_mae_C"],
        "zero_baseline_mae_C": round(float(np.abs(patches.targets[test_mask]).mean()), 5),
        "final_skill": round(state.best_skill, 4),
        "beats_predicting_nothing": bool(state.best_skill > 0),
        "train_seconds": round(elapsed, 1),
        "history": state.history,
    }
    listener.finished(report)
    return report


def _fresh_or_resumed(checkpoint: Path | None, trainables: Trainables, fingerprint: dict) -> TrainingState:
    """A fresh state, or the one a checkpoint holds when there is one to continue from."""
    if checkpoint is None:
        return TrainingState.fresh(trainables.model)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    if not checkpoint.exists():
        return TrainingState.fresh(trainables.model)
    state = TrainingState.load(checkpoint, trainables, fingerprint)
    logger.info("resuming after epoch %d from %s", state.epoch, checkpoint)
    return state


def _save_best(out_path: Path | None, state: TrainingState, channels: int) -> None:
    """Write the best epoch's weights, the only weights a model directory keeps."""
    if out_path is None:
        return
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": state.best_state, "in_channels": channels}, out_path)
