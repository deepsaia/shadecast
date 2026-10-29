"""Judge the trained surrogate against the physics it is standing in for.

Four questions, in the order that decides whether the surrogate is usable.

1. **Does it beat predicting nothing?** The response is near zero almost everywhere,
   so a low mean error proves nothing on its own. Skill against the zero baseline is
   the first gate, and a negative value means the model is worse than useless.
2. **Does the tail survive?** Cooling reaches tens of metres, and that tail is the
   spillover the benchmark exists to measure. A model that nails the near field and
   flattens the tail would pass on mean error and fail at the job.
3. **Is the plan score right?** Plans are ranked on population weighted exposure,
   which integrates the whole field, so that integral has to be unbiased.
4. **Does it order plans correctly?** A search only needs to know which of two plans
   is better. Biased but monotone is fine; unbiased but scrambled is worthless.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import torch

from ..exposure import outdoor_mask
from ..exposure import outdoor_weights
from . import manifest
from .assessment_inputs import AssessmentInputs
from .features import CHANNEL_SETS
from .features import channel_set_for
from .features import select
from .features import stack
from .metrics import aggregate_error
from .metrics import distance_bands
from .metrics import ranking
from .metrics import skill
from .metrics import speedup
from .patches import entries
from .patches import tile_key
from .predict import load
from .predict import predict_field
from .scene import Scene

logger = logging.getLogger(__name__)

ENGINE_SECONDS_REFERENCE = 162.0


def designs_for_tile(held_out: list[str], label: str) -> list[str]:
    """The held-out design ids that belong to this tile, with any ``label/`` prefix removed.

    A model trained on one tile records bare ids. A pooled model records ``city:tile/id``, so
    assessing it against one tile means keeping that tile's designs only.
    """
    chosen = []
    for design in held_out:
        if "/" not in design:
            chosen.append(design)
            continue
        prefix, name = design.split("/", 1)
        if prefix == label:
            chosen.append(name)
    return chosen


def channel_names(model_dir: Path, in_channels: int) -> tuple[str, ...]:
    """The channels the model was trained on: from its manifest, else from its channel count."""
    if (Path(model_dir) / manifest.MANIFEST_FILE).exists():
        return manifest.channel_names(manifest.read(model_dir))
    return CHANNEL_SETS[channel_set_for(in_channels)]


def _held_out(model_dir: Path) -> list[str]:
    """The designs the manifest says were held out; none when the model has no manifest."""
    if not (Path(model_dir) / manifest.MANIFEST_FILE).exists():
        return []
    return [str(design) for design in manifest.read(model_dir).get("data", {}).get("held_out_designs", [])]


def assess(inputs: AssessmentInputs, device: torch.device | None = None) -> dict:
    """Compare surrogate predictions against engine truth on the given designs."""
    physics_dir, bundle = Path(inputs.physics_dir), Path(inputs.bundle)
    checkpoint = Path(inputs.model_dir) / "model.pt"
    if not checkpoint.exists():
        raise FileNotFoundError(f"no trained model at {checkpoint}")

    held_out = _held_out(inputs.model_dir)
    wanted = inputs.only if inputs.only else designs_for_tile(held_out, tile_key(bundle))
    if not wanted:
        raise RuntimeError("no held-out designs recorded; train first")

    scene = Scene.load(bundle, physics_dir)
    outdoor = outdoor_mask(scene.building_height)
    weights = outdoor_weights(scene.population, scene.building_height)
    model = load(checkpoint, device)
    names = channel_names(Path(inputs.model_dir), model.in_channels)
    target_device = device or next(model.parameters()).device

    per_design: list[dict] = []
    truth_scores: list[float] = []
    predicted_scores: list[float] = []
    total_seconds = 0.0

    known = {meta["id"] for meta in entries(physics_dir)}
    for design_id in wanted:
        if design_id not in known:
            logger.warning("design %s not present in %s, skipping", design_id, physics_dir)
            continue
        payload = np.load(physics_dir / design_id / "response.npz")
        placement, truth = payload["placement"], payload["response"]

        features = select(stack(placement, scene), names)
        started = time.perf_counter()
        predicted = predict_field(model, features, target_device)
        elapsed = time.perf_counter() - started
        total_seconds += elapsed

        per_design.append(
            {
                "design": design_id,
                "coverage": round(float(placement.mean()), 5),
                "skill": skill(truth[outdoor], predicted[outdoor]),
                "aggregate": aggregate_error(truth, predicted, weights),
                "bands": distance_bands(truth, predicted, placement),
                "surrogate_seconds": round(elapsed, 4),
            }
        )
        truth_scores.append(per_design[-1]["aggregate"]["truth_C"])
        predicted_scores.append(per_design[-1]["aggregate"]["predicted_C"])

    if not per_design:
        raise RuntimeError("no designs could be assessed")

    mean_seconds = total_seconds / len(per_design)
    return {
        "model": str(inputs.model_dir),
        "city": bundle.parent.name if bundle.name == "bundle" else bundle.name,
        "designs_assessed": [d["design"] for d in per_design],
        "device": str(target_device),
        "headline": {
            "mean_skill": round(float(np.mean([d["skill"]["skill"] for d in per_design])), 4),
            "all_beat_predicting_nothing": all(d["skill"]["beats_predicting_nothing"] for d in per_design),
            "mean_aggregate_relative_error": round(
                float(np.mean([d["aggregate"]["relative_error"] for d in per_design])), 4
            ),
        },
        "ranking": ranking(truth_scores, predicted_scores),
        "speed": speedup(ENGINE_SECONDS_REFERENCE, mean_seconds),
        "per_design": per_design,
    }
