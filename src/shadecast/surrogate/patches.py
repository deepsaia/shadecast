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
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

from .features import stack

logger = logging.getLogger(__name__)

NEAR_INTERVENTION_M = 80.0


def load_city(bundle: Path, surrogate_dir: Path) -> dict:
    """Read the static layers and the baseline response for one city."""
    bundle, surrogate_dir = Path(bundle), Path(surrogate_dir)
    with rasterio.open(bundle / "Building_DSM.tif") as src:
        building_dsm = src.read(1)
    with rasterio.open(bundle / "DEM.tif") as src:
        terrain = src.read(1)
    with rasterio.open(bundle / "Trees.tif") as src:
        canopy = src.read(1)
    with rasterio.open(bundle / "landcover.tif") as src:
        land_cover = src.read(1)
    baseline = np.load(surrogate_dir / "baseline" / "tmrt_daylight.npy")
    return {
        "building_height": np.maximum(building_dsm - terrain, 0),
        "canopy": canopy,
        "land_cover": land_cover,
        "baseline_tmrt": baseline,
    }


def entries(surrogate_dir: Path) -> list[dict]:
    """Every generated response in a surrogate directory."""
    manifest = Path(surrogate_dir) / "manifest.json"
    if manifest.exists():
        return json.loads(manifest.read_text())["manifest"]
    found = []
    for meta in sorted(Path(surrogate_dir).glob("*/meta.json")):
        found.append(json.loads(meta.read_text()))
    return found


def sampling_weights(placement: np.ndarray, res_m: float = 1.0) -> np.ndarray:
    """Probability surface favouring the neighbourhood of an intervention."""
    # distance_transform_edt is overloaded and can return indices, so narrow it.
    distance = np.asarray(ndimage.distance_transform_edt(~placement), dtype="float64") * res_m
    near = (distance <= NEAR_INTERVENTION_M).astype("float64")
    # Keep a floor so far-field behaviour is still represented, since predicting a
    # true zero far away is part of the job.
    weights = near + 0.05
    return weights / weights.sum()


def crop_cities(
    pairs: list[tuple[Path, Path]],
    size: int = 256,
    per_entry: int = 24,
    seed: int = 0,
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
    for index, (surrogate_dir, bundle) in enumerate(pairs):
        inputs, targets, origins = crop_batch(
            surrogate_dir, bundle, size=size, per_entry=per_entry, seed=seed + index
        )
        city = Path(bundle).name
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
    surrogate_dir: Path, bundle: Path, size: int = 256, per_entry: int = 24, seed: int = 0
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build an (N, 7, size, size) input array and its (N, 1, size, size) targets."""
    city = load_city(bundle, surrogate_dir)
    rng = np.random.default_rng(seed)
    inputs: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    origins: list[str] = []

    for meta in entries(surrogate_dir):
        payload = np.load(Path(surrogate_dir) / meta["id"] / "response.npz")
        placement, response = payload["placement"], payload["response"]
        features = stack(
            placement,
            city["baseline_tmrt"],
            building_height=city["building_height"],
            canopy_height=city["canopy"],
            land_cover=city["land_cover"],
        )
        weights = sampling_weights(placement)
        rows, cols = response.shape

        flat = rng.choice(weights.size, size=per_entry, p=weights.ravel())
        for index in flat:
            row, col = divmod(int(index), cols)
            row = int(np.clip(row - size // 2, 0, rows - size))
            col = int(np.clip(col - size // 2, 0, cols - size))
            inputs.append(features[:, row : row + size, col : col + size])
            targets.append(response[None, row : row + size, col : col + size])
            origins.append(meta["id"])

    if not inputs:
        raise RuntimeError(f"no generated responses found in {surrogate_dir}")
    return np.stack(inputs), np.stack(targets), origins
