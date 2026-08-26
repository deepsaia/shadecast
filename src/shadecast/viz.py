"""Render result fields as pure-data images.

Deliberately no titles, axes, tick labels or colour bars are baked into the raster.
The page that embeds these supplies all text and legends in HTML, so the figures
stay legible in both light and dark themes and the labels stay selectable.

Two rules the maps must not break:

**Compared panels share a colour scale.** Two cooling fields drawn on independent
scales would look equally effective while differing fourfold, which is the exact
comparison these figures exist to make.

**The cooling ramp is non-linear, and the caption must say so.** Cooling is near
zero over most of the field with peaks near 28 C, so a linear ramp renders almost
entirely as background. A power norm is applied to make the structure visible; a
silently non-linear scale would be misleading.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, PowerNorm
from scipy import ndimage

# Headless rendering. Set after importing pyplot, which modern matplotlib supports,
# so the import block stays in conventional order.
matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# Single hue, light to dark, monotonic lightness. Never a rainbow.
COOLING_CMAP = LinearSegmentedColormap.from_list(
    "cooling", ["#f4f7fb", "#b9d3ef", "#6ba3de", "#2a78d6", "#17457c"]
)
HEAT_CMAP = LinearSegmentedColormap.from_list(
    "heat", ["#fdf3e7", "#f7c99a", "#eb8f4e", "#d1552a", "#7e2412"]
)
PLACEMENT_CMAP = LinearSegmentedColormap.from_list("placement", ["#00000000", "#1baf7a"])

COOLING_GAMMA = 0.45


def _save(figure: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=100, bbox_inches="tight", pad_inches=0, transparent=True)
    plt.close(figure)
    return path


def _bare_axes(size_px: int = 600) -> tuple[plt.Figure, plt.Axes]:
    figure = plt.figure(figsize=(size_px / 100, size_px / 100))
    axes = figure.add_axes((0, 0, 1, 1))
    axes.set_axis_off()
    return figure, axes


def field(
    values: np.ndarray,
    path: Path,
    *,
    vmax: float,
    cmap,
    gamma: float | None = None,
    buildings: np.ndarray | None = None,
    size_px: int = 600,
) -> Path:
    """Draw one raster field, with optional building fabric for orientation."""
    figure, axes = _bare_axes(size_px)
    norm = PowerNorm(gamma=gamma, vmin=0.0, vmax=vmax) if gamma else None
    axes.imshow(
        np.clip(values, 0, vmax),
        cmap=cmap,
        norm=norm,
        vmin=None if norm else 0.0,
        vmax=None if norm else vmax,
        interpolation="nearest",
    )
    if buildings is not None:
        # Fabric as a faint overlay so the reader can orient without it competing.
        axes.imshow(
            np.ma.masked_where(buildings <= 0, buildings),
            cmap="Greys",
            alpha=0.22,
            interpolation="nearest",
        )
    return _save(figure, path)


def cooling(
    values: np.ndarray,
    path: Path,
    *,
    vmax: float,
    buildings: np.ndarray | None = None,
    size_px: int = 600,
) -> Path:
    return field(
        values,
        path,
        vmax=vmax,
        cmap=COOLING_CMAP,
        gamma=COOLING_GAMMA,
        buildings=buildings,
        size_px=size_px,
    )


def temperature(
    values: np.ndarray, path: Path, *, vmin: float, vmax: float, size_px: int = 600
) -> Path:
    figure, axes = _bare_axes(size_px)
    axes.imshow(values, cmap=HEAT_CMAP, vmin=vmin, vmax=vmax, interpolation="nearest")
    return _save(figure, path)


def placement(
    mask: np.ndarray, path: Path, *, buildings: np.ndarray | None = None, size_px: int = 600
) -> Path:
    """Where the trees went. Dilated so single pixels remain visible when downscaled."""
    figure, axes = _bare_axes(size_px)
    if buildings is not None:
        axes.imshow(
            np.ma.masked_where(buildings <= 0, buildings),
            cmap="Greys",
            alpha=0.30,
            interpolation="nearest",
        )
    visible = ndimage.binary_dilation(mask, iterations=2)
    axes.imshow(
        np.ma.masked_where(~visible, visible.astype(float)),
        cmap=PLACEMENT_CMAP,
        vmin=0,
        vmax=1,
        interpolation="nearest",
    )
    return _save(figure, path)
