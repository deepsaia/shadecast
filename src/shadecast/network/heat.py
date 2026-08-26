"""Sample the Tmrt field onto street network edges.

The engine produces heat per square metre of ground. Routing needs heat per metre of
walkable street, so every edge is sampled along its own geometry rather than at its
midpoint. Midpoint sampling is tempting and wrong: a 120 m block that passes through
one deep shade pocket and 100 m of open sun averages to something no walker meets.
"""

from __future__ import annotations

import logging

import networkx as nx
import numpy as np
from shapely.geometry import LineString

from ..aoi import AOI

logger = logging.getLogger(__name__)

# Sampling step along an edge. Half the 1 m raster pitch would be wasteful; 2 m is
# about one walking pace and keeps a typical city block at 40 to 60 samples.
STEP_M = 2.0


def _edge_line(graph: nx.MultiDiGraph, u: int, v: int, data: dict) -> LineString:
    """Edge geometry, falling back to the straight line between its end nodes."""
    geom = data.get("geometry")
    if isinstance(geom, LineString):
        return geom
    return LineString(
        [(graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])]
    )


def _sample(line: LineString, field: np.ndarray, aoi: AOI, step_m: float) -> float:
    """Mean field value along a projected line, ignoring samples off the grid."""
    n = max(2, int(line.length / step_m) + 1)
    points = [line.interpolate(d, normalized=True) for d in np.linspace(0.0, 1.0, n)]
    minx, _, _, maxy = aoi.bounds_utm
    cols = np.array([(p.x - minx) / aoi.res_m for p in points], dtype=np.int64)
    rows = np.array([(maxy - p.y) / aoi.res_m for p in points], dtype=np.int64)
    height, width = field.shape
    inside = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
    if not inside.any():
        return float("nan")
    values = field[rows[inside], cols[inside]]
    return float(np.nanmean(values)) if np.isfinite(values).any() else float("nan")


def annotate(
    graph: nx.MultiDiGraph, tmrt: np.ndarray, aoi: AOI, *, step_m: float = STEP_M
) -> nx.MultiDiGraph:
    """Attach mean Tmrt to every edge, in place, and report coverage.

    Edges that fall entirely outside the raster keep NaN and are reported, rather than
    quietly defaulting to something comfortable that would make the plan look good.
    """
    missing = 0
    for u, v, key, data in graph.edges(keys=True, data=True):
        value = _sample(_edge_line(graph, u, v, data), tmrt, aoi, step_m)
        graph.edges[u, v, key]["tmrt"] = value
        if not np.isfinite(value):
            missing += 1
    total = graph.number_of_edges()
    if missing:
        logger.warning("%d of %d edges had no Tmrt coverage", missing, total)
    else:
        logger.info("sampled Tmrt onto %d edges", total)
    return graph
