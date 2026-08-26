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
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .model import ResponseUNet

logger = logging.getLogger(__name__)

HUBER_DELTA = 1.0


def pick_device() -> torch.device:
    """Prefer Apple GPU, then CUDA, then CPU."""
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


def train(
    inputs: np.ndarray,
    targets: np.ndarray,
    origins: list[str],
    *,
    epochs: int = 30,
    batch_size: int = 8,
    learning_rate: float = 2e-3,
    holdout: float = 0.25,
    seed: int = 0,
    out_path: Path | None = None,
) -> dict:
    """Fit the surrogate and report held-out error."""
    device = pick_device()
    torch.manual_seed(seed)

    train_mask, test_mask = split_by_design(origins, holdout=holdout, seed=seed)
    held_designs = sorted(set(np.array(origins)[test_mask].tolist()))
    logger.info(
        "device %s, %d train patches, %d held out across %d unseen designs",
        device,
        int(train_mask.sum()),
        int(test_mask.sum()),
        len(held_designs),
    )

    x_train = torch.from_numpy(inputs[train_mask]).float()
    y_train = torch.from_numpy(targets[train_mask]).float()
    x_test = torch.from_numpy(inputs[test_mask]).float().to(device)
    y_test = torch.from_numpy(targets[test_mask]).float().to(device)

    model = ResponseUNet().to(device)
    optimiser = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=epochs)
    criterion = nn.HuberLoss(delta=HUBER_DELTA)

    history: list[dict] = []
    started = time.time()
    for epoch in range(1, epochs + 1):
        model.train()
        order = torch.randperm(len(x_train))
        running = 0.0
        for start in range(0, len(order), batch_size):
            batch = order[start : start + batch_size]
            xb = x_train[batch].to(device)
            yb = y_train[batch].to(device)
            optimiser.zero_grad(set_to_none=True)
            loss = criterion(model(xb), yb)
            loss.backward()
            optimiser.step()
            running += loss.item() * len(batch)
        schedule.step()

        model.eval()
        with torch.no_grad():
            predicted = torch.cat(
                [model(x_test[i : i + batch_size]) for i in range(0, len(x_test), batch_size)]
            )
            mae = float((predicted - y_test).abs().mean())
            # Error of the trivial model that predicts no change anywhere. The
            # response is near zero over most of the field, so a low absolute error
            # proves nothing on its own and every number must be read against this.
            baseline_mae = float(y_test.abs().mean())
        history.append(
            {
                "epoch": epoch,
                "train_loss": running / max(1, len(x_train)),
                "test_mae_C": mae,
                "skill": 1.0 - mae / max(baseline_mae, 1e-12),
            }
        )
        if epoch % 5 == 0 or epoch == 1:
            logger.info(
                "epoch %2d: train loss %.4f, held-out MAE %.4f C, skill %+.3f",
                epoch,
                history[-1]["train_loss"],
                mae,
                history[-1]["skill"],
            )

    elapsed = time.time() - started
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": model.state_dict(), "in_channels": inputs.shape[1]}, out_path)

    return {
        "device": str(device),
        "epochs": epochs,
        "train_patches": int(train_mask.sum()),
        "test_patches": int(test_mask.sum()),
        "held_out_designs": held_designs,
        "final_test_mae_C": history[-1]["test_mae_C"],
        "zero_baseline_mae_C": round(float(np.abs(targets[test_mask]).mean()), 5),
        "final_skill": round(history[-1]["skill"], 4),
        "beats_predicting_nothing": bool(history[-1]["skill"] > 0),
        "train_seconds": round(elapsed, 1),
        "history": history,
        "checkpoint": str(out_path) if out_path else None,
    }


def save_report(report: dict, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2))
