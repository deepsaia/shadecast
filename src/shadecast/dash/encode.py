"""Ship raster fields as data, not as pictures.

The walkthrough used to serve one rendered PNG per hour, which meant the colour ramp was
baked in, the browser fetched a new file on every scrub, and a visitor could look at a
pixel without ever learning what temperature it was.

Here a field is quantised to one byte per pixel and packed into a single greyscale PNG
holding every frame. PNG is doing its real job, lossless compression of a smooth
two-dimensional array, and is decoded in the browser back into numbers. The colour ramp
is then applied on a canvas at draw time, so hovering can report degrees, the scale can
change without a round trip, and 24 hours cost one request rather than 24.

Value 0 is reserved for "no data" so masked ground stays transparent instead of
rendering as the coldest colour, which would be a quiet lie about a missing pixel.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

NODATA = 0
LEVELS = 255


def quantise(field: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
    """Map a float field onto 1..255, reserving 0 for missing."""
    span = max(vmax - vmin, 1e-9)
    scaled = (np.asarray(field, dtype=np.float64) - vmin) / span
    bytes_ = np.clip(np.round(scaled * (LEVELS - 1)), 0, LEVELS - 1).astype(np.uint8) + 1
    return np.where(np.isfinite(field), bytes_, NODATA).astype(np.uint8)


def downsample(field: np.ndarray, size: int) -> np.ndarray:
    """Area-average to exactly `size` on the long side.

    Area averaging rather than nearest: these fields are noisy at pixel scale, and
    nearest sampling keeps that noise, which costs real bytes because PNG cannot
    compress it. It also aliases thin shade into speckle.
    """
    height, width = field.shape
    if max(height, width) <= size:
        return field
    scale = size / max(height, width)
    target = (max(1, round(width * scale)), max(1, round(height * scale)))
    image = Image.fromarray(np.asarray(field, dtype=np.float32), mode="F")
    return np.asarray(image.resize(target, Image.Resampling.BOX), dtype=np.float64)


def atlas(fields: list[np.ndarray], path: Path, *, size: int = 400, columns: int = 6) -> dict:
    """Pack many fields into one greyscale PNG and describe how to read it back."""
    if not fields:
        return {}
    tiles = [downsample(np.asarray(f, dtype=np.float64), size) for f in fields]
    finite = np.concatenate([t[np.isfinite(t)].ravel() for t in tiles])
    vmin, vmax = float(finite.min()), float(finite.max())

    height, width = tiles[0].shape
    rows = int(np.ceil(len(tiles) / columns))
    sheet = np.zeros((rows * height, columns * width), dtype=np.uint8)
    for index, tile in enumerate(tiles):
        r, c = divmod(index, columns)
        sheet[r * height : (r + 1) * height, c * width : (c + 1) * width] = quantise(
            tile, vmin, vmax
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet, mode="L").save(path, optimize=True)
    logger.info(
        "atlas %s: %d frames at %dx%d, %.0f KB",
        path.name,
        len(tiles),
        width,
        height,
        path.stat().st_size / 1024,
    )
    return {
        "file": path.name,
        "tile_w": width,
        "tile_h": height,
        "columns": columns,
        "rows": rows,
        "count": len(tiles),
        "vmin": round(vmin, 3),
        "vmax": round(vmax, 3),
    }
