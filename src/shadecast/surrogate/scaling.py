"""Does training on more cities improve transfer to an unseen one?

This is the question that decides whether shadecast is a benchmark or a single city
demonstration, and it is worth answering as a curve rather than a single comparison.

Hold one city out entirely. Train on one of the remaining cities, then two, then
three, and measure skill on the held out city each time. A rising curve means more
cities buy transfer and the corpus should be scaled. A flat curve means the
architecture is the limit, not the data, and no amount of physics will fix it.

Each point is an independent training run, so the curve costs roughly five minutes
per point plus the physics already generated for each city.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .patches import crop_cities
from .training import train

logger = logging.getLogger(__name__)


def city_of(bundle: Path) -> str:
    return Path(bundle).name


def transfer_curve(
    pairs: list[tuple[Path, Path]],
    holdout_city: str,
    *,
    epochs: int = 40,
    patch: int = 256,
    per_entry: int = 32,
    seed: int = 0,
) -> dict:
    """Skill on `holdout_city` as a function of how many cities were trained on."""
    held = [p for p in pairs if city_of(p[1]) == holdout_city]
    if not held:
        raise ValueError(f"{holdout_city!r} is not among {[city_of(p[1]) for p in pairs]}")
    others = [p for p in pairs if city_of(p[1]) != holdout_city]
    if not others:
        raise ValueError("need at least one training city besides the holdout")

    points: list[dict] = []
    for count in range(1, len(others) + 1):
        subset = others[:count]
        names = [city_of(p[1]) for p in subset]
        logger.info("training on %d cities %s, testing on %s", count, names, holdout_city)

        inputs, targets, origins = crop_cities(
            [*subset, *held], size=patch, per_entry=per_entry, seed=seed
        )
        report = train(
            inputs,
            targets,
            origins,
            epochs=epochs,
            holdout_city=holdout_city,
            seed=seed,
            out_path=None,
        )
        points.append(
            {
                "n_train_cities": count,
                "train_cities": names,
                "skill": report["final_skill"],
                "mae_C": round(report["final_test_mae_C"], 4),
                "zero_baseline_mae_C": report["zero_baseline_mae_C"],
                "train_patches": report["train_patches"],
            }
        )
        logger.info("  %d cities -> skill %+.3f", count, report["final_skill"])

    skills = [p["skill"] for p in points]
    verdict = "insufficient evidence"
    if len(skills) >= 2:
        gain = skills[-1] - skills[0]
        # A gain worth scaling for. Below this the curve is flat within the noise of
        # a single training run and more physics would be wasted.
        verdict = "more cities help" if gain > 0.05 else "flat, architecture is the limit"

    return {
        "holdout_city": holdout_city,
        "points": points,
        "skill_gain": round(float(skills[-1] - skills[0]), 4) if len(skills) >= 2 else None,
        "verdict": verdict,
    }


def save(report: dict, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2))
