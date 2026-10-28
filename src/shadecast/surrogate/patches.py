"""Turn generated response fields into training patches.

One engine call produces a full square kilometre of response, which is a million
pixels of signal. Cropping it into patches turns each call into thousands of
training examples, and is why a plan of 17 physics runs is enough to fit a model.

Patches are sampled with a bias towards places where something happened. A uniform
crop over a field that is 95 percent near-zero would spend almost all its capacity
learning to predict zero.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy import ndimage

from .features import select, stack
from .patch_settings import PatchSettings
from .scene import Scene

logger = logging.getLogger(__name__)

NEAR_INTERVENTION_M = 80.0
FAR_FIELD_FLOOR = 0.05


def tile_key(bundle: Path) -> str:
    """``city:tile`` for a bundle in the tile layout, else the bundle directory's name.

    Origins are ``key/design``, and a city holdout matches the part before the colon, so one
    key names a whole city and ``city:tile`` names one of its tiles.
    """
    provenance_path = Path(bundle) / "provenance.json"
    if not provenance_path.exists():
        return Path(bundle).name
    provenance = json.loads(provenance_path.read_text())
    city = provenance.get("city", {}).get("key")
    tile = provenance.get("tile", {}).get("id")
    if city and tile:
        return f"{city}:{tile}"
    return str(city or Path(bundle).name)


def entries(physics_dir: Path) -> list[dict]:
    """Every generated response in a surrogate directory."""
    manifest = Path(physics_dir) / "manifest.json"
    if manifest.exists():
        return json.loads(manifest.read_text())["manifest"]
    found = []
    for meta in sorted(Path(physics_dir).glob("*/meta.json")):
        found.append(json.loads(meta.read_text()))
    return found


def sampling_weights(placement: np.ndarray, res_m: float = 1.0) -> np.ndarray:
    """Probability surface favouring the neighbourhood of an intervention."""
    # distance_transform_edt is overloaded and can return indices, so narrow it.
    distance = np.asarray(ndimage.distance_transform_edt(~placement), dtype="float64") * res_m
    near = (distance <= NEAR_INTERVENTION_M).astype("float64")
    # Keep a floor so far-field behaviour is still represented, since predicting a
    # true zero far away is part of the job.
    weights = near + FAR_FIELD_FLOOR
    return weights / weights.sum()


def crop_cities(
    pairs: list[tuple[Path, Path]], settings: PatchSettings
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Crop patches from several cities into one training set.

    Origins are tagged ``city/design`` so a split can hold out either a design
    within a city, which measures generalisation to an unseen intervention, or a
    whole city, which measures transfer. Those are different questions and the
    benchmark reports both.
    """
    all_inputs: list[np.ndarray] = []
    all_targets: list[np.ndarray] = []
    all_origins: list[str] = []
    for index, (physics_dir, bundle) in enumerate(pairs):
        inputs, targets, origins = crop_batch(
            physics_dir, bundle, replace(settings, seed=settings.seed + index)
        )
        city = tile_key(bundle)
        all_inputs.append(inputs)
        all_targets.append(targets)
        all_origins.extend(f"{city}/{origin}" for origin in origins)
        logger.info("%s: %d patches from %d designs", city, len(inputs), len(set(origins)))
    return (
        np.concatenate(all_inputs),
        np.concatenate(all_targets),
        all_origins,
    )


def crop_batch(
    physics_dir: Path, bundle: Path, settings: PatchSettings
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build an (N, channels, size, size) input array and its (N, 1, size, size) targets."""
    scene = Scene.load(bundle, physics_dir)
    rng = np.random.default_rng(settings.seed)
    size = settings.size
    inputs: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    origins: list[str] = []

    for meta in entries(physics_dir):
        payload = np.load(Path(physics_dir) / meta["id"] / "response.npz")
        placement, response = payload["placement"], payload["response"]
        features = select(stack(placement, scene), settings.names)
        weights = sampling_weights(placement)
        rows, cols = response.shape

        flat = rng.choice(weights.size, size=settings.per_entry, p=weights.ravel())
        for index in flat:
            row, col = divmod(int(index), cols)
            row = int(np.clip(row - size // 2, 0, rows - size))
            col = int(np.clip(col - size // 2, 0, cols - size))
            inputs.append(features[:, row : row + size, col : col + size])
            targets.append(response[None, row : row + size, col : col + size])
            origins.append(meta["id"])

    if not inputs:
        raise RuntimeError(f"no generated responses found in {physics_dir}")
    return np.stack(inputs), np.stack(targets), origins
