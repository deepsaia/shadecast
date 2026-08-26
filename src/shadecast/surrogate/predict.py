"""Run the trained surrogate over a whole city.

The model is fully convolutional, so it can be applied to a full study area in one
pass when memory allows, and tiled with overlap when it does not. Tiles are blended
with a cosine window rather than butt-joined, because a visible seam in the response
field would corrupt the spatial statistics the benchmark scores on.

This is the module that turns the surrogate from a trained artifact into something
that can stand in for an engine call inside a search loop.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import rasterio
import torch

from ..data.landcover import to_umep  # noqa: F401  (kept so callers can featurise)
from .features import stack
from .model import ResponseUNet

logger = logging.getLogger(__name__)

# A 1000 by 1000 field at width 32 fits comfortably in unified memory; beyond that
# tiling keeps peak memory flat regardless of city size.
FULL_FIELD_LIMIT_PX = 1400
TILE_PX = 512
TILE_OVERLAP_PX = 64


def load(checkpoint: Path, device: torch.device | None = None) -> ResponseUNet:
    """Restore a trained response model."""
    target = device or torch.device("cpu")
    payload = torch.load(checkpoint, map_location=target, weights_only=True)
    model = ResponseUNet(in_channels=payload.get("in_channels", 7))
    model.load_state_dict(payload["state_dict"])
    model.eval().to(target)
    return model


def blend_window(size: int, overlap: int) -> np.ndarray:
    """A separable cosine taper so overlapping tiles sum to one."""
    ramp = 0.5 * (1 - np.cos(np.linspace(0, np.pi, overlap)))
    profile = np.ones(size)
    profile[:overlap] = ramp
    profile[-overlap:] = ramp[::-1]
    return np.outer(profile, profile)


def _forward(model: ResponseUNet, features: np.ndarray, device: torch.device) -> np.ndarray:
    tensor = torch.from_numpy(features[None]).float().to(device)
    with torch.no_grad():
        return model(tensor)[0, 0].cpu().numpy()


def predict_field(
    model: ResponseUNet, features: np.ndarray, device: torch.device | None = None
) -> np.ndarray:
    """Predict the response field for a full (7, H, W) feature stack."""
    target = device or next(model.parameters()).device
    _, rows, cols = features.shape

    if max(rows, cols) <= FULL_FIELD_LIMIT_PX:
        # Pad to a multiple of the downsampling factor so the skips line up.
        factor = 2**model.depth
        pad_r = (-rows) % factor
        pad_c = (-cols) % factor
        padded = np.pad(features, ((0, 0), (0, pad_r), (0, pad_c)), mode="reflect")
        return _forward(model, padded, target)[:rows, :cols]

    accumulated = np.zeros((rows, cols), dtype="float64")
    weights = np.zeros((rows, cols), dtype="float64")
    window = blend_window(TILE_PX, TILE_OVERLAP_PX)
    step = TILE_PX - TILE_OVERLAP_PX

    for row_start in range(0, max(1, rows - TILE_OVERLAP_PX), step):
        for col_start in range(0, max(1, cols - TILE_OVERLAP_PX), step):
            # Clamp so the last tile in each direction sits flush with the edge
            # rather than running past it.
            top = min(row_start, max(0, rows - TILE_PX))
            left = min(col_start, max(0, cols - TILE_PX))
            tile = features[:, top : top + TILE_PX, left : left + TILE_PX]
            if tile.shape[1] < TILE_PX or tile.shape[2] < TILE_PX:
                continue
            predicted = _forward(model, tile, target)
            accumulated[top : top + TILE_PX, left : left + TILE_PX] += predicted * window
            weights[top : top + TILE_PX, left : left + TILE_PX] += window

    return np.divide(accumulated, weights, out=np.zeros_like(accumulated), where=weights > 0)


def predict_for_bundle(
    checkpoint: Path,
    bundle: Path,
    placement: np.ndarray,
    baseline_tmrt: np.ndarray,
    device: torch.device | None = None,
) -> tuple[np.ndarray, float]:
    """Predict the cooling field for one placement over a built bundle.

    Returns the field and the wall clock seconds it took, which is the number that
    matters when comparing against a 162 second engine call.
    """
    bundle = Path(bundle)
    with rasterio.open(bundle / "Building_DSM.tif") as src:
        building_dsm = src.read(1)
    with rasterio.open(bundle / "DEM.tif") as src:
        terrain = src.read(1)
    with rasterio.open(bundle / "Trees.tif") as src:
        canopy = src.read(1)
    with rasterio.open(bundle / "landcover.tif") as src:
        land_cover = src.read(1)

    model = load(checkpoint, device)
    features = stack(
        placement,
        baseline_tmrt,
        building_height=np.maximum(building_dsm - terrain, 0),
        canopy_height=canopy,
        land_cover=land_cover,
    )
    started = time.perf_counter()
    field = predict_field(model, features, device)
    return field, time.perf_counter() - started
