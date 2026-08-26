"""Turn per-edge corridor value into a planting surface the planner can rank.

The planner chooses pixels. The network objective produces numbers on edges. This is
the join between them: an edge worth cooling becomes a band of ground worth planting,
widened to the reach over which a tree actually shades the street it stands beside.

The value is spread per metre of edge rather than dumped whole, so a long block does
not outrank a short one purely by being long. Length is already accounted for inside
the corridor figure, and counting it twice would bias every plan toward arterials.
"""

from __future__ import annotations

import logging

import networkx as nx
import numpy as np
from scipy.ndimage import grey_dilation
from shapely.geometry import LineString

from ..aoi import AOI

logger = logging.getLogger(__name__)

# How far from a street a tree can still shade it. A mature crown reaches roughly this
# far, and it is also about the width of the footway a walker is actually on.
BUFFER_M = 6.0
STEP_M = 2.0


def _disk(radius_px: int) -> np.ndarray:
    span = np.arange(-radius_px, radius_px + 1)
    rows, cols = np.meshgrid(span, span, indexing="ij")
    return (rows**2 + cols**2) <= radius_px**2


def corridor_surface(
    graph: nx.DiGraph,
    corridor: dict[tuple[int, int], float],
    aoi: AOI,
    *,
    buffer_m: float = BUFFER_M,
    step_m: float = STEP_M,
) -> np.ndarray:
    """Paint corridor value onto the ground beside each edge.

    Returns a float surface on the AOI grid, in the same units as `corridor`, which are
    shares of total trip heat.
    """
    height, width = aoi.shape
    surface = np.zeros((height, width), dtype=np.float64)
    minx, _, _, maxy = aoi.bounds_utm

    for (u, v), value in corridor.items():
        if value <= 0 or not graph.has_edge(u, v):
            continue
        line = LineString(
            [(graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])]
        )
        n = max(2, int(line.length / step_m) + 1)
        points = [line.interpolate(d, normalized=True) for d in np.linspace(0.0, 1.0, n)]
        share = value / n
        for point in points:
            col = int((point.x - minx) / aoi.res_m)
            row = int((maxy - point.y) / aoi.res_m)
            if 0 <= row < height and 0 <= col < width:
                surface[row, col] += share

    painted = int((surface > 0).sum())
    if painted == 0:
        logger.warning("no corridor value landed on the grid")
        return surface

    radius_px = max(1, round(buffer_m / aoi.res_m))
    widened = grey_dilation(surface, footprint=_disk(radius_px))
    logger.info(
        "corridor surface: %d street pixels widened to %d plantable pixels",
        painted,
        int((widened > 0).sum()),
    )
    return widened
