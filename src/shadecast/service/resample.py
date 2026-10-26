"""Shrink a field to a requested size by area averaging, one band or a stack of them."""

from __future__ import annotations

import numpy as np
from PIL import Image


def downsample(field: np.ndarray, size: int) -> np.ndarray:
    """Area-average to exactly ``size`` on the long side; a smaller field comes back as is.

    Area averaging rather than nearest: these fields are noisy at pixel scale, and nearest
    sampling keeps that noise and aliases thin shade into speckle.
    """
    height, width = field.shape
    if max(height, width) <= size:
        return field
    scale = size / max(height, width)
    target = (max(1, round(width * scale)), max(1, round(height * scale)))
    image = Image.fromarray(np.asarray(field, dtype=np.float32), mode="F")
    return np.asarray(image.resize(target, Image.Resampling.BOX), dtype=np.float64)


def downsample_stack(stack: np.ndarray, size: int) -> np.ndarray:
    """Every band of a (bands, height, width) stack, each shrunk the same way."""
    return np.stack([downsample(band, size) for band in stack])
